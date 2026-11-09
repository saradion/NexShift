from django.shortcuts import render

# Create your views here.
from django.db.models import Q
from notif.models import Notification
from notif.services import notify, notify_admins
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.jalali import to_jalali_str
from core.filters import JalaliDateFilter
from core.permissions import IsAdminRole
from department.models import Department, Skill
from core.jalali import to_jalali_str
from notif.models import Notification
from notif.services import notify, notify_admins
from .models import LeaveRequest, Nurse
from .serializers import (
    LeaveRequestSerializer,
    LeaveReviewSerializer,
    NurseSerializer,
    NurseWriteSerializer,
)


class NurseFilter(filters.FilterSet):
    skill = filters.ModelChoiceFilter(field_name="skills", queryset=Skill.objects.all())
    eligible_for_department = filters.ModelChoiceFilter(
        queryset=Department.objects.all(), method="filter_eligible"
    )

    class Meta:
        model = Nurse
        fields = ["home_department", "employment_type", "is_active", "can_work_nights"]

    def filter_eligible(self, queryset, name, value):
        return queryset.filter(Q(home_department=value) | Q(allowed_departments=value)).distinct()


class NurseViewSet(viewsets.ModelViewSet):

    queryset = Nurse.objects.all()
    filterset_class = NurseFilter
    search_fields = ["personnel_code", "user__first_name", "user__last_name", "user__username"]
    ordering_fields = ["personnel_code", "experience_years", "hire_date"]

    def get_queryset(self):
        qs = Nurse.objects.select_related("user", "home_department").prefetch_related(
            "allowed_departments", "nurse_skills__skill"
        )
        user = self.request.user
        return qs if user.is_scheduler else qs.filter(user=user)

    def get_permissions(self):
        if self.action in ("list", "retrieve", "me"):
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return NurseWriteSerializer
        return NurseSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        instance.user.is_active = False
        instance.user.save(update_fields=["is_active"])

    @action(detail=False, methods=["get"])
    def me(self, request):
        nurse = get_object_or_404(self.get_queryset(), user=request.user)
        return Response(NurseSerializer(nurse, context=self.get_serializer_context()).data)


class LeaveRequestFilter(filters.FilterSet):
    from_date = JalaliDateFilter(field_name="end_date", lookup_expr="gte")
    to_date = JalaliDateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = LeaveRequest
        fields = ["status", "leave_type", "nurse"]


class LeaveRequestViewSet(viewsets.ModelViewSet):

    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    filterset_class = LeaveRequestFilter
    search_fields = ["nurse__personnel_code", "nurse__user__first_name", "nurse__user__last_name"]
    ordering_fields = ["start_date", "created_at"]

    def get_queryset(self):
        qs = LeaveRequest.objects.select_related("nurse__user", "reviewed_by")
        user = self.request.user
        return qs if user.is_scheduler else qs.filter(nurse__user=user)

    def get_permissions(self):
        if self.action in ("approve", "reject"):
            return [IsAdminRole()]
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        leave = serializer.save()
        period = f"{to_jalali_str(leave.start_date)} to {to_jalali_str(leave.end_date)}"
        if self.request.user.is_scheduler:
            notify([leave.nurse.user], "Leave registered for you", f"Leave {period}.",
                    kind=Notification.Kind.LEAVE, related=leave)
        else:
            notify_admins("New leave request", f"{leave.nurse.full_name} requested leave {period}.",
                    kind=Notification.Kind.LEAVE, related=leave)

    @staticmethod
    def _assert_editable(request, leave):
        if not request.user.is_scheduler and leave.status != LeaveRequest.Status.PENDING:
            raise PermissionDenied("Only pending requests can be modified.")

    def perform_update(self, serializer):
        self._assert_editable(self.request, serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._assert_editable(self.request, instance)
        instance.delete()

    def _review(self, request, new_status):
        leave = self.get_object()
        if leave.status != LeaveRequest.Status.PENDING:
            return Response(
                {"detail": f"Only pending requests can be reviewed (current status: {leave.status})."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = LeaveReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave.status = new_status
        leave.reviewed_by = request.user
        leave.reviewed_at = timezone.now()
        leave.review_note = serializer.validated_data.get("review_note", "")
        leave.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
        return Response(self.get_serializer(leave).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._review(request, LeaveRequest.Status.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._review(request, LeaveRequest.Status.REJECTED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        leave = self.get_object()
        if leave.status in (LeaveRequest.Status.REJECTED, LeaveRequest.Status.CANCELLED):
            return Response({"detail": f"Request is already {leave.status}."}, status=status.HTTP_409_CONFLICT)
        if not request.user.is_scheduler and leave.status != LeaveRequest.Status.PENDING:
            raise PermissionDenied("Only pending requests can be cancelled. Contact the scheduler.")
        leave.status = LeaveRequest.Status.CANCELLED
        leave.save(update_fields=["status", "updated_at"])
        
        """notify(
            [leave.nurse.user],
            f"Leave request {new_status}",
            f"Your leave from {to_jalali_str(leave.start_date)} to {to_jalali_str(leave.end_date)} was {new_status}."
            + (f" Note: {leave.review_note}" if leave.review_note else ""),
            kind=Notification.Kind.LEAVE,
            related=leave,
        )"""
        
        return Response(self.get_serializer(leave).data)