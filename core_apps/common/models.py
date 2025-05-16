import uuid
from typing import Any, Optional
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models, IntegrityError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

User = get_user_model()


class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ContentView(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="content_views",
        verbose_name=_("User"),
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField(verbose_name=_("Object ID"))
    content_object = models.GenericForeignKey("content_type", "object_id")
    viewer_ip = models.GenericIPAddressField(
        verbose_name=_("Viewer IP"), null=True, blank=True
    )
    last_viewed_at = models.DateTimeField(verbose_name=_("Last Viewed At"))

    class Meta:
        verbose_name = _("Content View")
        verbose_name_plural = _("Content Views")
        unique_together = ("user", "content_type", "object_id", "viewer_ip")

    def __str__(self) -> str:
        return (
            f"{self.user.get_full_name() if self.user else 'Anonymous'} viewed "
            f"{self.content_object} at {self.created_at} with IP {self.viewer_ip}"
        )

    @classmethod
    def record_view(
        cls,
        content_object: Any,
        user: Optional[User],
        viewer_ip: Optional[str] = None,
    ) -> None:
        content_type = ContentType.objects.get_for_model(content_object)
        try:
            view, created = cls.objects.get_or_create(
                content_type=content_type,
                object_id=content_object.id,
                defaults={
                    "last_viewed_at": timezone.now(),
                    "user": user,
                    "viewer_ip": viewer_ip,
                },
            )
            if not created:
                view.last_viewed_at = timezone.now()
                view.save()
        except IntegrityError:
            pass
