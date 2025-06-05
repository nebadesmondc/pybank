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
