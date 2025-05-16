from django.contrib import admin
from typing import Any
from django.contrib.contenttypes.admin import GenericTabularInline
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from .models import ContentView


@admin.register(ContentView)
class ContentViewAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "content_object",
        "content_type",
        "last_viewed_at",
        "viewer_ip",
        "created_at",
    ]
    list_filter = ["content_type", "last_viewed_at", "created_at"]
    readonly_fields = [
        "user",
        "content_object",
        "content_type",
        "viewer_ip",
        "object_id",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "content_object",
                    "content_type",
                    "object_id",
                )
            },
        ),
        (
            _("View Details"),
            {
                "fields": (
                    "user",
                    "viewer_ip",
                    "last_viewed_at",
                )
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class ContentViewInline(GenericTabularInline):
    model = ContentView
    readonly_fields = ["user", "viewer_ip", "last_viewed", "created_at"]
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
