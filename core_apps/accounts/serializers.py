from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import BankAccount, Transaction


class AccountVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "kyc_submitted",
            "kyc_approved",
            "verification_date",
            "verification_notes",
            "fully_activated",
            "account_status",
        ]
        read_only_fields = ["fully_activated"]

    def validate(self, data: dict) -> dict:
        kyc_approved = data.get("kyc_approved")
        kyc_submitted = data.get("kyc_submitted")
        verification_date = data.get("verification_date")
        verification_notes = data.get("verification_notes")

        if kyc_approved:
            if not verification_date:
                raise serializers.ValidationError(
                    {"verification_date": _("This field is required.")}
                )
            if not verification_notes:
                raise serializers.ValidationError(
                    {"verification_notes": _("This field is required.")}
                )

            if kyc_submitted and not all(
                [kyc_approved, verification_date, verification_notes]
            ):
                raise serializers.ValidationError(
                    {
                        "verification_date": _("This field is required."),
                        "verification_notes": _("This field is required."),
                    }
                )
        return data


class DepositSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.1")
    )

    class Meta:
        model = BankAccount
        fields = ["account_number", "amount"]

    def validate_account_number(self, value: str) -> str:
        try:
            account = BankAccount.objects.get(account_number=value)
            self.context["account"] = account
        except BankAccount.DoesNotExist:
            raise serializers.ValidationError(
                {"account_number": _("Account number does not exist.")}
            )
        return value

    def to_representation(self, instance: BankAccount) -> str:
        representation = super().to_representation(instance)
        representation["amount"] = str(representation["amount"])
        return representation


class CustomerInfoSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(source="user.fullname")
    email = serializers.EmailField(source="user.email")
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = [
            "account_number",
            "fullname",
            "email",
            "photo_url" "account_type",
            "account_balance",
            "currency",
        ]

    def get_photo_url(self, obj) -> str:
        if hasattr(obj.user, "profile") and obj.user.profile.photo_url:
            return obj.user.profile.photo_url
        return None


class UUIDField(serializers.Field):
    def to_representation(self, value):
        return str(value)


class TransactionSerializer(serializers.ModelSerializer):
    id = UUIDField(read_only=True)
    sender_account = serializers.CharField(max_length=20, required=False)
    receiver_account = serializers.CharField(max_length=20, required=False)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.1")
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "description",
            "status",
            "transaction_type",
            "created_at",
            "sender",
            "receiver",
            "sender_account",
            "receiver_account",
        ]
        read_only_fields = ["id", "created_at", "status"]

    def to_representation(self, instance: Transaction) -> str:
        representation = super().to_representation(instance)
        representation["amount"] = str(representation["amount"])
        representation["sender"] = instance.sender.fullname if instance.sender else None
        representation["receiver"] = (
            instance.receiver.fullname if instance.receiver else None
        )
        representation["sender_account"] = (
            instance.sender_account.account_number if instance.sender_account else None
        )
        representation["receiver_account"] = (
            instance.receiver_account.account_number if instance.receiver else None
        )

        return representation

    def validate(self, data):
        transaction_type = data.get("transaction_type")
        sender_account = data.get("sender_account")
        receiver_account = data.get("receiver_account")
        amount = data.get("amount")

        try:
            if transaction_type == Transaction.TransactionType.WITHDRAWAL:
                account = BankAccount.objects.get(account_number=sender_account)
                data["sender_account"] = account
                data["receiver_account"] = None
                if account.account_balance < amount:
                    raise serializers.ValidationError(
                        "Insufficient funds for withdrawal"
                    )
                elif transaction_type == Transaction.TransactionType.DEPOSIT:
                    account = BankAccount.objects.get(account_number=receiver_account)
                    data["receiver_account"] = account
                    data["sender_account"] = None
                else:
                    sender_account = BankAccount.objects.get(
                        account_number=sender_account
                    )
                    receiver_account = BankAccount.objects.get(
                        account_number=receiver_account
                    )
                    data["sender_account"] = sender_account
                    data["receiver_account"] = receiver_account

                    if sender_account == receiver_account:
                        raise serializers.ValidationError(
                            "Sender and receiver accounts cannot be the same"
                        )
                    if sender_account.currency != receiver_account.currency:
                        raise serializers.ValidationError(
                            "Sender and receiver accounts must have the same currency"
                        )
                    if sender_account.account_balance < amount:
                        raise serializers.ValidationError(
                            "Insufficient funds for transfer"
                        )

        except BankAccount.DoesNotExist:
            raise serializers.ValidationError("One or both accounts not found")
        return data


class SecurityQuestionSerializer(serializers.Serializer):
    security_answer = serializers.CharField(max_length=30)

    def validate(self, data: dict) -> dict:
        user = self.context["request"].user
        if data["security_answer"] != user.security_answer:
            raise serializers.ValidationError("Incorrect security answer.")

        return data


class OTPVerificationSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6)

    def validate(self, data: dict) -> dict:
        user = self.context["request"].user
        if not user.verify_otp(data["otp"]):
            raise serializers.ValidationError("Invalid or expired OTP")

        return data


class UsernameVerificationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=12)

    def validate_username(self, value: dict) -> dict:
        user = self.context["request"].user
        if not user.username != value:
            raise serializers.ValidationError("Invalid username")

        return value
