from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from loguru import logger

from core_apps.accounts.models import BankAccount


def send_account_creation_email(user, bank_account):
    subject = _("Your New Bank Account has Created")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    context = {"user": user, "account": bank_account, "site_name": settings.SITE_NAME}
    html_content = render_to_string("emails/account_created.html", context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
        logger.info(f"Account Created email send to: {user.email}")
    except Exception as e:
        logger.error(
            f"Failed to send Account Created email to: {user.email}: Error {str(e)}"
        )


def send_full_activation_email(account: BankAccount) -> None:
    subject = _("Your Bank Account has been Activated")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [account.user.email]
    context = {"account": account, "site_name": settings.SITE_NAME}
    html_content = render_to_string("emails/bank_account_activated.html", context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
        logger.info(f"Account Activated email send to: {account.user.email}")
    except Exception as e:
        logger.error(
            f"Failed to send Account Activated email to: {account.user.email}: Error {str(e)}"
        )


def send_deposit_email(
    fullname, user_email, amount, currency, new_balance, account_number
):
    subject = _("Deposit Successful")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]
    context = {
        "fullname": fullname,
        "amount": amount,
        "currency": currency,
        "new_balance": new_balance,
        "account_number": account_number,
        "site_name": settings.SITE_NAME,
    }
    html_content = render_to_string("emails/deposit_confirmation.html", context)
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
    email.attach_alternative(html_content, "text/html")
    try:
        email.send()
        logger.info(f"Deposit Successful email send to: {user_email}")
    except Exception as e:
        logger.error(
            f"Failed to send Deposit Successful email to: {user_email}: Error {str(e)}"
        )
