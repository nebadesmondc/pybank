import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from .emails import send_account_locked_email
from .managers import UserManager


class User(AbstractUser):
    class SecurityQuestions(models.TextChoices):
        FAVORITE_COLOR = (
            "favorite_color",
            _("What is your favorite color?"),
        )
        PET_NAME = (
            "pet_name",
            _("What is the name of your pet?"),
        )
        BIRTH_CITY = (
            "birth_city",
            _("What city were you born in?"),
        )
        FAVORITE_SPORT = (
            "favorite_sport",
            _("What is your favorite sport?"),
        )

    class AccountStatus(models.TextChoices):
        ACTIVE = (
            "active",
            _("Active"),
        )
        LOCKED = (
            "locked",
            _("Locked"),
        )

    class RoleChoices(models.TextChoices):
        CUSTOMER = (
            "customer",
            _("Customer"),
        )
        ACCOUNT_EXECUTIVE = (
            "account_executive",
            _("Account Executive"),
        )
        TELLER = (
            "teller",
            _("Teller"),
        )
        BRANCH_MANAGER = (
            "branch_manager",
            _("Branch Manager"),
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    security_answer = models.CharField(_("Security Answer"), max_length=30)
    username = models.CharField(_("Username"), max_length=12, unique=True)
    email = models.EmailField(_("Email Address"), unique=True, db_index=True)
    first_name = models.CharField(_("First Name"), max_length=30)
    middle_name = models.CharField(
        _("Middle Name"), max_length=30, blank=True, null=True
    )
    last_name = models.CharField(_("Last Name"), max_length=30)
    security_question = models.CharField(
        _("Security Question"),
        max_length=30,
        choices=SecurityQuestions.choices,
    )
    id_no = models.CharField(_("ID Number"), max_length=20, unique=True)
    account_status = models.CharField(
        _("Account Status"),
        max_length=10,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )
    role = models.CharField(
        _("Role"),
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.CUSTOMER,
    )
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    otp = models.CharField(_("OTP"), max_length=6, null=True, blank=True)
    otp_expiry_time = models.DateTimeField(_("OTP Expiry Time"), null=True, blank=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = [
        "first_name",
        "last_name",
        "id_no",
        "security_question",
        "security_answer",
    ]

    def set_otp(self, otp: str) -> None:
        self.otp = (otp,)
        self.otp_expiry_time = timezone.now() + settings.OTP_EXPIRATION
        self.save()

    def verify_otp(self, otp: str) -> bool:
        if self.otp == otp and self.otp_expiry_time > timezone.now():
            self.otp = ""
            self.otp_expiry_time = None
            self.save()
            return True
        return False

    def handle_failed_login_attempt(self) -> None:
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        if self.failed_login_attempts >= settings.LOGIN_ATTEMPTS:
            self.account_status = self.AccountStatus.LOCKED
            self.save()
            send_account_locked_email(self.email)
        self.save()

    def reset_failed_login_attempts(self) -> None:
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.account_status = self.AccountStatus.ACTIVE
        self.save()

    def unlock_account(self) -> None:
        if self.account_status == self.AccountStatus.LOCKED:
            self.account_status = self.AccountStatus.ACTIVE
            self.failed_login_attempts = 0
            self.last_failed_login = None
            self.save()

    @property
    def is_locked_out(self) -> bool:
        if self.account_status == self.AccountStatus.LOCKED:
            lockout_duration = settings.LOCKOUT_DURATION
            if self.last_failed_login:
                time_since_last_attempt = timezone.now() - self.last_failed_login
                if time_since_last_attempt > lockout_duration:
                    self.unlock_account()
                    return False
            return True
        return False

    @property
    def fullname(self) -> str:
        if self.middle_name:
            return (
                f"{self.first_name} {self.middle_name} {self.last_name}".title().strip()
            )
        return f"{self.first_name} {self.last_name}".title().strip()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]

    def has_role(self, role_name: str) -> bool:
        return hasattr(self, "role") and self.role == role_name

    def __str__(self) -> str:
        return f"{self.fullname} - {self.get_role_display()}"
