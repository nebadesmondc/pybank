from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from core_apps.common.models import TimeStampedModel
from decimal import Decimal, ROUND_HALF_UP
from loguru import logger

User = get_user_model()


class BankAccount(TimeStampedModel):
    class AccountType(models.TextChoices):
        CURRENT = "current", _("Current")
        SAVINGS = "savings", _("Savings")
        CREDIT = "credit", _("Credit")
        DEBIT = "debit", _("Debit")

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        CLOSED = "closed", _("Closed")

    class AccountCurrency(models.TextChoices):
        USD = "usd", _("USD")
        EUR = "eur", _("EUR")
        XAF = "xaf", _("XAF")

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bank_accounts"
    )
    account_number = models.CharField(_("Account Number"), max_length=20, unique=True)
    account_balance = models.DecimalField(
        _("Account Balance"), max_digits=10, decimal_places=2, default=0.00
    )
    currency = models.CharField(
        _("Currency"),
        max_length=3,
        choices=AccountCurrency.choices,
        default=AccountCurrency.XAF,
    )
    account_status = models.CharField(
        _("Account Status"),
        max_length=10,
        choices=AccountStatus.choices,
        default=AccountStatus.INACTIVE,
    )
    account_type = models.CharField(
        _("Account Type"),
        max_length=10,
        choices=AccountType.choices,
        default=AccountType.CURRENT,
    )
    is_primary = models.BooleanField(_("Primary Account"), default=False)
    kyc_submitted = models.BooleanField(_("KYC Submitted"), default=False)
    kyc_approved = models.BooleanField(_("KYC Approved"), default=False)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="verified_accounts",
        null=True,
        blank=True,
    )
    verification_date = models.DateTimeField(
        _("Verification Date"), null=True, blank=True
    )
    verification_notes = models.TextField(
        _("Verification Notes"), null=True, blank=True
    )
    fully_activated = models.BooleanField(_("Fully Activated"), default=False)
    interest_rate = models.DecimalField(
        _("Interest Rate"),
        max_digits=5,
        decimal_places=4,
        default=0.00,
        help_text=_("Annual interest rate as a decimal (e.g 0.020 for 2.0%)"),
    )

    def __str__(self) -> str:
        return (
            f"{self.user.fullname}'s - {self.get_currency_display()} - "
            f"{self.get_account_type_display()} Account - {self.account_number}"
        )

    @property
    def annual_interest_rate(self):
        if self.account_type != self.AccountType.SAVINGS:
            return Decimal("0.0000")

        balance = self.account_balance
        if balance < Decimal("100000"):
            return Decimal("0.0050")
        elif Decimal("100000") <= balance < Decimal("500000"):
            return Decimal("0.0100")
        elif Decimal("500000") <= balance < Decimal("1000000"):
            return Decimal("0.0150")
        else:
            return Decimal("0.0200")

    def apply_daily_interest(self):
        if self.account_type == self.AccountType.SAVINGS:
            daily_interest_rate = self.annual_interest_rate / Decimal("365")
            interest = (Decimal(self.account_balance) * daily_interest_rate).quantize(
                Decimal(".01"), rounding=ROUND_HALF_UP
            )
            logger.info(
                f"Applying daily interest {interest} to account {self.account_number}"
            )
            self.account_balance += interest
            self.save()

            Transaction.objects.create(
                user=self.user,
                amount=interest,
                description="Daily interest applied",
                receiver=self.user,
                sender=self.user,
                receiver_account=self,
                status=Transaction.TransactionStatus.COMPLETED,
                transaction_type=Transaction.TransactionType.INTEREST,
            )
            return interest
        return Decimal("0.00")

    class Meta:
        verbose_name = _("Bank Account")
        verbose_name_plural = _("Bank Accounts")
        unique_together = ("user", "currency", "account_type")

    def clean(self) -> None:
        if self.account_balance < 0:
            raise ValidationError(_("Account balance cannot be negative."))

    def save(self, *args, **kwargs) -> None:
        if self.is_primary:
            BankAccount.objects.filter(user=self.user).update(is_primary=False)
        super().save(*args, **kwargs)


class Transaction(TimeStampedModel):
    class TransactionStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")

    class TransactionType(models.TextChoices):
        INTEREST = "interest", _("Interest")
        DEPOSIT = "deposit", _("Deposit")
        WITHDRAWAL = "withdrawal", _("Withdrawal")
        TRANSFER = "transfer", _("Transfer")

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="transactions"
    )
    amount = models.DecimalField(
        _("Amount"), max_digits=12, decimal_places=2, default=0.00
    )
    description = models.TextField(
        _("Description"), null=True, blank=True, max_length=500
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_transactions",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_transactions",
    )
    receiver_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_transactions",
    )
    sender_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_transactions",
    )
    status = models.CharField(
        choices=TransactionStatus.choices,
        max_length=20,
        default=TransactionStatus.PENDING,
    )
    transaction_type = models.CharField(
        choices=TransactionType.choices, max_length=20, default=TransactionType.DEPOSIT
    )

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.status}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at"])]
