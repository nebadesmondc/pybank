import random
from decimal import Decimal
from typing import Any

from dateutil import parser
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from loguru import logger
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from core_apps.common.permissions import IsAccountExecutive, IsTeller
from core_apps.common.renderers import GenericJSONRenderer
from .emails import (
    send_full_activation_email,
    send_deposit_email,
    send_transfer_otp_email,
    send_transfer_email,
)
from .models import BankAccount, Transaction
from .tasks import generate_transaction_pdf
from .pagination import StandardResultsSetPagination
from .serializers import (
    AccountVerificationSerializer,
    CustomerInfoSerializer,
    DepositSerializer,
    TransactionSerializer,
    SecurityQuestionSerializer,
    OTPVerificationSerializer,
)


class AccountVerificationView(generics.UpdateAPIView):
    queryset = BankAccount.objects.all()
    serializer_class = AccountVerificationSerializer
    permission_classes = [IsAccountExecutive]
    renderer_classes = [GenericJSONRenderer]
    object_label = "verification"

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()

        if instance.kyc_approved and instance.fully_activated:
            return Response(
                {"message": "Account is already fully activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if serializer.is_valid(raise_exception=True):
            kyc_submitted = serializer.validated_data.get(
                "kyc_submitted", instance.kyc_submitted
            )

            kyc_approved = serializer.validated_data.get(
                "kyc_approved", instance.kyc_approved
            )

            if kyc_approved and not kyc_submitted:
                return Response(
                    {"error": "KYC must be submitted before it can be verified."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            instance.kyc_submitted = kyc_submitted
            instance.save()

            if kyc_submitted and kyc_approved:
                instance.kyc_approved = kyc_approved
                instance.verification_date = serializer.validated_data.get(
                    "verification_date", timezone.now()
                )
                instance.verification_notes = serializer.validated_data.get(
                    "verification_notes", ""
                )
                instance.approved_by = request.user
                instance.fully_activated = True
                instance.account_status = BankAccount.AccountStatus.ACTIVE
                instance.save()

                send_full_activation_email(instance)

            return Response(
                {
                    "message": "Account Verification status updated successfully",
                    "data": self.get_serializer(instance).data,
                }
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DepositView(generics.CreateAPIView):
    serializer_class = DepositSerializer
    permission_classes = [IsTeller]
    renderer_classes = [GenericJSONRenderer]
    object_label = "deposit"

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        account_number = request.query_params.get("account_number")
        if not account_number:
            return Response(
                {"error": "Account number is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            account = BankAccount.objects.get(account_number=account_number)
            serializer = CustomerInfoSerializer(account)
            return Response(serializer.data)
        except BankAccount.DoesNotExist:
            return Response(
                {"error": "Account does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @transaction.atomic
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.context["account"]
        amount = serializer.validated_data["amount"]

        try:
            account.account_balance += amount
            account.full_clean()
            account.save()

            logger.info(
                f"Deposit of {amount} made to account {account.account_number} by "
                f"Teller {request.user.email}"
            )

            send_deposit_email(
                fullname=account.user.fullname,
                user_email=account.user.email,
                amount=amount,
                account_number=account.account_number,
                new_balance=account.account_balance,
                currency=account.currency,
            )

            return Response(
                {
                    "message": f"Successfully deposited { amount } to account {account.account_number}",
                    "new_balance": str(account.account_balance),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error during deposit: {e}")
            return Response(
                {"error": "An error occurred during the deposit."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InitiateTransferView(generics.CreateAPIView):
    serializer_class = TransactionSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "initiate_transfer"

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = request.data.copy()
        data["transaction_type"] = Transaction.TransactionType.TRANSFER

        sender_account = data.get("sender_account")
        receiver_account = data.get("receiver_account")

        try:
            sender = BankAccount.objects.get(
                account_number=sender_account, user=request.user
            )
            if not (sender.fully_activated and sender.kyc_approved):
                return Response(
                    {
                        "error": "Sender account is not fully verified. "
                        "Please complete the verification process by visiting any of our local branches"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except BankAccount.DoesNotExist:
            return Response(
                {
                    "error": "Sender account number does not exist."
                    " Or you are not authorized to use this account"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            request.session["transfer_data"] = {
                "sender_account": sender_account,
                "receiver_account": receiver_account,
                "amount": str(serializer.validated_data["amount"]),
                "description": serializer.validated_data["description"],
            }

            return Response(
                {
                    "message": "Please answer the security Question to proceed with the transfer",
                    "nect_step": "verify security question",
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifySecurityQuestionView(generics.CreateAPIView):
    serializer_class = SecurityQuestionSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "verify_security_question"

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
            request.user.set_otp(otp)
            send_transfer_otp_email(request.user.email, otp)

            return Response(
                {
                    "message": "OTP sent to your email. Please enter the OTP to proceed with the transfer",
                    "next_step": "verify otp",
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(generics.CreateAPIView):
    serializer_class = OTPVerificationSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "verify_otp"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            return self.process_transfer(request)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def process_transfer(self, request) -> Response:
        transfer_data = request.session.get("transfer_data")
        if not transfer_data:
            return Response(
                {"error": "Transfer data not found. Please start a new transfer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            sender_account = BankAccount.objects.get(
                account_number=transfer_data["sender_account"]
            )
            receiver_account = BankAccount.objects.get(
                account_number=transfer_data["receiver_account"]
            )
        except BankAccount.DoesNotExist:
            return Response(
                {"error": "Sender or receiver account not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        amount = Decimal(transfer_data["amount"])

        if sender_account.account_balance < amount:
            return Response(
                {"error": "Insufficient funds."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sender_account.account_balance -= amount
        receiver_account.account_balance += amount
        sender_account.save()
        receiver_account.save()

        transfer_transaction = Transaction.objects.create(
            user=request.user,
            sender=request.user,
            sender_account=sender_account,
            receiver=receiver_account.user,
            receiver_account=receiver_account,
            amount=amount,
            description=transfer_data["description"],
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=Transaction.TransactionStatus.COMPLETED,
        )

        del request.session["transfer_data"]
        send_transfer_email(
            sender_name=sender_account.user.fullname,
            sender_email=sender_account.user.email,
            receiver_name=receiver_account.user.fullname,
            receiver_email=receiver_account.user.email,
            amount=amount,
            currency=sender_account.currency,
            sender_new_balance=sender_account.account_balance,
            receiver_new_balance=receiver_account.account_balance,
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
        )

        logger.info(
            f"Transfer of {amount} from account {sender_account.account_number} to "
            f"account {receiver_account.account_number} initiated by {request.user.email}"
        )

        return Response(
            TransactionSerializer(transfer_transaction).data,
            status=status.HTTP_201_CREATED,
        )


class TransactionListApiView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.filter(Q(sender=user) | Q(receiver=user))
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        account_number = self.request.query_params.get("account_number")

        if start_date:
            try:
                start_date = parser.parse(start_date)
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass
        if end_date:
            try:
                end_date = parser.parse(end_date)
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                pass
        if account_number:
            try:
                account = BankAccount.objects.get(
                    account_number=account_number, user=user
                )
                queryset = queryset.filter(
                    Q(sender_account=account) | Q(receiver_account=account)
                )
            except BankAccount.DoesNotExist:
                queryset = Transaction.objects.none()
        return queryset

    def list(self, request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)

        account_number = request.query_params.get("account_number")
        if account_number:
            logger.info(
                f"User {request.user.email} retrieved transactions for account {account_number}"
            )
        else:
            logger.info(f"User {request.user.email} retrieved all transactions")

        return response


class TransactionPDFView(APIView):
    renderer_classes = [GenericJSONRenderer]
    object_label = "transaction_pdf"

    def post(self, request) -> Response:
        user = request.user
        start_date = request.data.get("start_date") or request.query_params.get(
            "start_date"
        )
        end_date = request.data.get("end_date") or request.query_params.get("end_date")
        account_number = request.data.get("account_number") or request.query_params.get(
            "account_number"
        )

        if not end_date:
            end_date = timezone.now().date().isoformat()

        if not start_date:
            start_date = (
                (parser.parse(end_date) - timezone.timedelta(days=30))
                .date()
                .isoformat()
            )
        try:
            start_date = parser.parse(start_date).date().isoformat()
            end_date = parser.parse(end_date).date().isoformat()
        except ValueError:
            return Response(
                {"error": "Invalid date format. Please use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        generate_transaction_pdf.delay(user.id, start_date, end_date, account_number)

        return Response(
            {"message": "PDF generation initiated. You will receive an email shortly."},
            status=status.HTTP_202_ACCEPTED,
        )
