from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import BankAccount
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = [
        "account_number",
        "user",
        "currency",
        "account_type",
        "account_balance",
        "account_status",
        "is_primary",
        "kyc_approved",
        "get_approved_by",
    ]
    search_fields = [
        "account_number",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]
    list_filter = [
        "account_type",
        "account_status",
        "currency",
        "is_primary",
        "kyc_approved",
        "kyc_submitted",
    ]
    readonly_fields = ["account_number", "created_at", "updated_at"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "account_number",
                    "account_balance",
                    "account_type",
                    "currency",
                    "is_primary",
                )
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "account_status",
                    "kyc_submitted",
                    "kyc_approved",
                    "verification_date",
                    "verification_notes",
                    "fully_activated",
                )
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_approved_by(self, obj):
        return obj.approved_by.full_name if obj.approved_by else "-"

    get_approved_by.short_description = _("Approved By")
    get_approved_by.admin_order_field = "approved_by__full_name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(approved_by=request.user)

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True
        return request.user.is_superuser or obj.approved_by == request.user

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "approved_by":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
