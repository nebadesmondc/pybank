from django.urls import path
from .views import (
    AccountVerificationView,
    DepositView,
    InitiateTransferView,
    VerifySecurityQuestionView,
    VerifyOTPView,
)

urlpatterns = [
    path("verify/<uuid:pk>/", AccountVerificationView.as_view(), name="verify-account"),
    path("deposit/", DepositView.as_view(), name="account-deposit"),
    path(
        "transfer/initiate/", InitiateTransferView.as_view(), name="initiate-transfer"
    ),
    path(
        "transfer/verify-security-question/",
        VerifySecurityQuestionView.as_view(),
        name="verify-security-question",
    ),
    path("transfer/verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
]
