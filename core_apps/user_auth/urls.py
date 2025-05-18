from django.urls import path

from .views import (
    CustomTokenCreateView,
    CustomTokenRefreshView,
    LogoutView,
    OTPVerifyView,
)

urlpatterns = [
    path("login/", CustomTokenCreateView.as_view(), name="login"),
    path("refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("verify-otp/", OTPVerifyView.as_view(), name="verify-otp"),
]
