from django.urls import path

from .views import (
    NextOfKinListApiView,
    NextOfKinDetailApiView,
    ProfileListApiView,
    ProfileDetailApiView,
)

urlpatterns = [
    path("", ProfileListApiView.as_view(), name="profile-list"),
    path("my-profile/", ProfileDetailApiView.as_view(), name="profile-detail"),
    path(
        "my-profile/next-of-kin/",
        NextOfKinListApiView.as_view(),
        name="next-of-kin-list",
    ),
    path(
        "my-profile/next-of-kin/<uuid:pk>/",
        NextOfKinDetailApiView.as_view(),
        name="next-of-kin-detail",
    ),
]
