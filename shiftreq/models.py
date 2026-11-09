
# Create your models here.
from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from department.models import ShiftType
from schedule.models import ShiftAssignment
from staff.models import Nurse


class ShiftRequest(TimeStampedModel):
    class RequestType(models.TextChoices):
        OBJECTION = "objection", "Objection"
        CHANGE = "change", "Change request"
        SWAP = "swap", "Swap / hand over"

    class Status(models.TextChoices):
        PENDING_PEER = "pending_peer", "Waiting for colleague"
        PENDING_ADMIN = "pending_admin", "Waiting for scheduler"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    requester = models.ForeignKey(Nurse, on_delete=models.CASCADE, related_name="shift_requests")
    request_type = models.CharField(max_length=10, choices=RequestType.choices)
    assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, related_name="shift_requests")

    # swap: target_nurse takes my shift; if target_assignment is set, I take theirs in exchange
    target_nurse = models.ForeignKey(Nurse, null=True, blank=True, on_delete=models.SET_NULL, related_name="incoming_requests")
    target_assignment = models.ForeignKey(ShiftAssignment, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    # change: optionally the date / shift type the nurse would like instead
    requested_date = models.DateField(null=True, blank=True)
    requested_shift_type = models.ForeignKey(ShiftType, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    reason = models.TextField()
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING_ADMIN)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_shift_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_request_type_display()} by {self.requester} [{self.status}]"