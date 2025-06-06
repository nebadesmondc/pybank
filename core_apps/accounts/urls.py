from django.urls import path
from .views import AccountVerificationView, DepositView

urlpatterns = [
    path("verify/<uuid:pk>/", AccountVerificationView.as_view(), name="verify-account"),
    path("deposit/", DepositView.as_view(), name="account-deposit"),
]
