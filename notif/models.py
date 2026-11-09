from django.db import models

# Create your models here.
from django.conf import settings
from django.utils import timezone

from core.models import TimeStampedModel


class Notification(TimeStampedModel):
    class Kind(models.TextChoices):
        INFO = "info", "Info"
        LEAVE = "leave", "Leave"
        SCHEDULE = "schedule", "Schedule"
        REQUEST = "request", "Request"
        ALERT = "alert", "Alert"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INFO)
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    related_type = models.CharField(max_length=50, blank=True)
    related_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])

    def __str__(self):
        return f"{self.recipient} - {self.title}"