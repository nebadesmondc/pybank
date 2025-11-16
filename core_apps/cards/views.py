from decimal import Decimal, InvalidOperation

from django.db import transaction
from loguru import logger
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core_apps.accounts.models import Transaction
from core_apps.common.renderers import GenericJSONRenderer
from .emails import send_virtual_card_topup_email
from .models import VirtualCard
from .serializers import VirtualCardCreateSerializer, VirtualCardSerializer


class VirtualCardListCreateAPIView(generics.ListCreateAPIView):
    renderer_classes = [GenericJSONRenderer]
    object_label = "visa_card"

    def get_queryset(self):
        user = self.request.user
        return VirtualCard.objects.filter(user=user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VirtualCardCreateSerializer
        return VirtualCardSerializer

    def create(self, request, *args, **kwargs) -> Response:
        if request.user.virtual_cards.count() >= 3:
            return Response(
                {"error": "You can only have 3 virtual cards at a time."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bank_account_number = serializer.validated_data["bank_account_number"]
        bank_account = request.user.bank_accounts.all()

        if not bank_account.filter(account_number=bank_account_number).exists():
            return Response(
                {
                    "error": "You can only create a virtual card linked to your own bank account"
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        virtual_card = serializer.save(user=request.user)
        logger.info(
            f"Virtual card number {virtual_card.card_number} created for user {request.user.username}"
        )
        return Response(
            VirtualCardSerializer(virtual_card).data,
            status=status.HTTP_201_CREATED,
        )


class VirtualCardDetailApiView(generics.RetrieveDestroyAPIView):
    renderer_classes = [GenericJSONRenderer]
    serializer_class = VirtualCardSerializer
    object_label = "visa_card"

    def get_queryset(self):
        user = self.request.user
        return VirtualCard.objects.filter(user=user)

    def get_object(self):
        obj = super().get_object()
        if obj.user != self.request.user:
            raise PermissionDenied(
                "You do not have permission to access this virtual card."
            )
        return obj

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.balance > Decimal("0.00"):
                return Response(
                    {
                        "error": "You cannot delete a virtual card with a balance greater than 0."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            super().perform_destroy(instance)
            logger.info(
                f"Virtual card number {instance.card_number} deleted for user {instance.user.fullname}"
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        except VirtualCard.DoesNotExist:
            return Response(
                {"error": "Virtual card not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            logger.error(f"Error during virtual card deletion: {str(e)}")
            return Response(
                {"error": "An error occurred during virtual card deletion."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VirtualCardTopUpAPIView(generics.UpdateAPIView):
    renderer_classes = [GenericJSONRenderer]
    object_label = "visa_card"

    def get_queryset(self):
        user = self.request.user
        return VirtualCard.objects.filter(user=user)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        virtual_card = self.get_object()
        amount = request.data.get("amount")

        if amount is None:
            return Response(
                {"error": "Amount is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            amount = Decimal(amount)
        except InvalidOperation:
            return Response(
                {"error": "Invalid top-up amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if amount <= 0:
            return Response(
                {"error": "Top-up amount must be greater than 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bank_account = virtual_card.bank_account
        if bank_account.account_balance < amount:
            return Response(
                {"error": "Insufficient funds in the linked bank account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bank_account.account_balance -= amount
        virtual_card.balance += amount
        bank_account.save()
        virtual_card.save()

        transaction = Transaction.objects.create(
            user=request.user,
            amount=amount,
            description=f"Top-up for Visa card ending in {virtual_card.card_number[-4:]}",
            transaction_type=Transaction.TransactionType.DEPOSIT,
            status=Transaction.TransactionStatus.COMPLETED,
            sender=request.user,
            receiver=request.user,
            sender_account=bank_account,
            receiver_account=bank_account,
        )
        send_virtual_card_topup_email(
            request.user, virtual_card, amount, virtual_card.balance
        )
        logger.info(
            f"Virtual card number {virtual_card.card_number} topped up with {amount} for user {request.user.fullname}. Transaction ID: {transaction.id}"
        )

        return Response(VirtualCardSerializer(virtual_card).data)
