

# Create your views here.
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.services import log_action
from core.permissions import IsAdminRole
from notif.models import Notification
from notif.services import notify, notify_admins
from schedule.views import describe

from .models import ShiftRequest
from .serializers import OPEN, ReviewNoteSerializer, ShiftRequestSerializer
from .services import apply_request

S = ShiftRequest.Status
KIND = Notification.Kind.REQUEST


class ShiftRequestViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ShiftRequestSerializer
    filterset_fields = ["request_type", "status", "requester"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        qs = ShiftRequest.objects.select_related(
            "requester__user", "target_nurse__user", "assignment__shift_type",
            "assignment__department", "assignment__schedule", "target_assignment",
        )
        user = self.request.user
        if user.is_scheduler:
            return qs
        return qs.filter(Q(requester__user=user) | Q(target_nurse__user=user))

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    # helpers
    @staticmethod
    def _conflict(message):
        return Response({"detail": message}, status=status.HTTP_409_CONFLICT)

    @staticmethod
    def _note(request):
        serializer = ReviewNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get("note", "")

    def _out(self, req):
        return Response(self.get_serializer(req).data)

    # create
    def perform_create(self, serializer):
        is_swap = serializer.validated_data["request_type"] == ShiftRequest.RequestType.SWAP
        req = serializer.save(status=S.PENDING_PEER if is_swap else S.PENDING_ADMIN)
        text = describe(req.assignment)
        if is_swap:
            notify([req.target_nurse.user], "Shift swap request",
                    f"{req.requester.full_name} asks you to take or swap: {text}. Reason: {req.reason}",
                    kind=KIND, related=req)
        else:
            notify_admins(f"New {req.get_request_type_display().lower()}",
                        f"{req.requester.full_name} - {text}. Reason: {req.reason}", kind=KIND, related=req)
        log_action(self.request.user, "request.create", req, f"{req.request_type}: {text}")

    #colleague answers (swap)
    def _peer_guard(self, request, req):
        if req.target_nurse is None or req.target_nurse.user_id != request.user.id:
            raise PermissionDenied("Only the colleague this request was sent to can answer it.")
        if req.status != S.PENDING_PEER:
            return self._conflict("This request is not waiting for a colleague.")
        return None

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        req = self.get_object()
        blocked = self._peer_guard(request, req)
        if blocked:
            return blocked
        req.status = S.PENDING_ADMIN
        req.save(update_fields=["status", "updated_at"])
        text = describe(req.assignment)
        notify_admins("Swap accepted by colleague", f"{req.requester.full_name} <-> {req.target_nurse.full_name}: {text}. Needs your approval.", kind=KIND, related=req)
        notify([req.requester.user], "Your swap request was accepted by your colleague", "Now waiting for the scheduler.", kind=KIND, related=req)
        return self._out(req)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        req = self.get_object()
        blocked = self._peer_guard(request, req)
        if blocked:
            return blocked
        req.status = S.REJECTED
        req.admin_note = self._note(request)
        req.save(update_fields=["status", "admin_note", "updated_at"])
        notify([req.requester.user], "Your swap request was declined", f"{req.target_nurse.full_name} declined.", kind=KIND, related=req)
        return self._out(req)

    #scheduler decides
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != S.PENDING_ADMIN:
            return self._conflict(f"Only requests waiting for the scheduler can be approved (current: {req.status}).")
        note = self._note(request)
        with transaction.atomic():
            errors = apply_request(req)
            if errors:
                return Response(
                    {"detail": "Approving this would break scheduling rules, so nothing was changed.", "errors": errors},
                    status=status.HTTP_409_CONFLICT,
                )
            req.status, req.reviewed_by, req.reviewed_at, req.admin_note = S.APPROVED, request.user, timezone.now(), note
            req.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note", "updated_at"])
        recipients = [req.requester.user] + ([req.target_nurse.user] if req.target_nurse else [])
        notify(recipients, "Shift request approved", f"{describe(req.assignment)}" + (f" Note: {note}" if note else ""), kind=KIND, related=req)
        log_action(request.user, "request.approve", req, f"Approved {req.request_type} #{req.pk}")
        return self._out(req)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        req = self.get_object()
        if req.status != S.PENDING_ADMIN:
            return self._conflict(f"Only requests waiting for the scheduler can be rejected (current: {req.status}).")
        req.status, req.reviewed_by, req.reviewed_at, req.admin_note = S.REJECTED, request.user, timezone.now(), self._note(request)
        req.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_note", "updated_at"])
        notify([req.requester.user], "Shift request rejected", f"{describe(req.assignment)}" + (f" Note: {req.admin_note}" if req.admin_note else ""), kind=KIND, related=req)
        log_action(request.user, "request.reject", req, f"Rejected {req.request_type} #{req.pk}")
        return self._out(req)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        req = self.get_object()
        if req.requester.user_id != request.user.id:
            raise PermissionDenied("Only the nurse who made the request can cancel it.")
        if req.status not in OPEN:
            return self._conflict("Only open requests can be cancelled.")
        req.status = S.CANCELLED
        req.save(update_fields=["status", "updated_at"])
        return self._out(req)