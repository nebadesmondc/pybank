from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import BankAccount


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
