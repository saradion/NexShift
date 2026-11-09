

# Create your views here.
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audit.services import log_action
from core.filters import JalaliDateFilter
from core.jalali import to_jalali_str
from core.mixins import ProtectedDeleteMixin
from core.permissions import IsAdminRole
from notif.models import Notification
from notif.services import notify

from .models import DemandRule, Schedule, ShiftAssignment, ShiftShortage
from .serializers import (
    DemandRuleSerializer,
    ScheduleSerializer,
    ShiftAssignmentSerializer,
    ShiftShortageSerializer,
)

User = get_user_model()


def describe(a: ShiftAssignment) -> str:
    return f"{to_jalali_str(a.date)} - {a.shift_type.name} - {a.department.name}"


class ScheduleFilter(filters.FilterSet):
    # overlapping window: ?from_date=1405-08-01&to_date=1405-08-30
    from_date = JalaliDateFilter(field_name="end_date", lookup_expr="gte")
    to_date = JalaliDateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = Schedule
        fields = ["status"]


class ScheduleViewSet(viewsets.ModelViewSet):
    """Admins: everything. Nurses: only published schedules, read-only."""

    serializer_class = ScheduleSerializer
    filterset_class = ScheduleFilter
    search_fields = ["name"]
    ordering_fields = ["start_date", "created_at"]

    def get_queryset(self):
        qs = Schedule.objects.annotate(
            assignment_count=Count("assignments", distinct=True),
            shortage_count=Count("shortages", distinct=True),
        )
        user = self.request.user
        return qs if user.is_scheduler else qs.filter(status=Schedule.Status.PUBLISHED)

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        schedule = serializer.save(created_by=self.request.user)
        log_action(self.request.user, "schedule.create", schedule, f"Created schedule {schedule.name}")

    def perform_update(self, serializer):
        if serializer.instance.status != Schedule.Status.DRAFT:
            raise ValidationError("Only draft schedules can be edited.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status == Schedule.Status.PUBLISHED:
            raise ValidationError("Archive a published schedule before deleting it.")
        log_action(self.request.user, "schedule.delete", instance, f"Deleted schedule {instance.name}")
        instance.delete()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        schedule = self.get_object()
        if schedule.status != Schedule.Status.DRAFT:
            return Response({"detail": "Only draft schedules can be published."}, status=status.HTTP_409_CONFLICT)
        if not schedule.assignments.exists():
            return Response({"detail": "This schedule has no assignments yet."}, status=status.HTTP_409_CONFLICT)
        overlapping = Schedule.objects.filter(
            status=Schedule.Status.PUBLISHED, start_date__lte=schedule.end_date, end_date__gte=schedule.start_date
        ).exclude(pk=schedule.pk)
        if overlapping.exists():
            return Response(
                {"detail": "Another published schedule overlaps this period. Archive it first."},
                status=status.HTTP_409_CONFLICT,
            )
        schedule.status = Schedule.Status.PUBLISHED
        schedule.published_at = timezone.now()
        schedule.save(update_fields=["status", "published_at", "updated_at"])

        users = User.objects.filter(nurse_profile__assignments__schedule=schedule).distinct()
        notify(
            users,
            "New schedule published",
            f"{schedule.name}: {to_jalali_str(schedule.start_date)} to {to_jalali_str(schedule.end_date)}. "
            "Open 'my shifts' to see yours.",
            kind=Notification.Kind.SCHEDULE,
            related=schedule,
        )
        log_action(request.user, "schedule.publish", schedule, f"Published {schedule.name}")
        return Response(ScheduleSerializer(schedule, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        schedule = self.get_object()
        if schedule.status == Schedule.Status.ARCHIVED:
            return Response({"detail": "Already archived."}, status=status.HTTP_409_CONFLICT)
        schedule.status = Schedule.Status.ARCHIVED
        schedule.save(update_fields=["status", "updated_at"])
        log_action(request.user, "schedule.archive", schedule, f"Archived {schedule.name}")
        return Response(ScheduleSerializer(schedule, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Copy a schedule (with its assignments) into a new draft, so you can try a different scenario."""
        source = self.get_object()
        name = str(request.data.get("name") or f"{source.name} (copy)")[:150]
        with transaction.atomic():
            copy = Schedule.objects.create(
                name=name, description=source.description, start_date=source.start_date,
                end_date=source.end_date, created_by=request.user,
            )
            ShiftAssignment.objects.bulk_create(
                [
                    ShiftAssignment(
                        schedule=copy, nurse_id=a.nurse_id, department_id=a.department_id,
                        shift_type_id=a.shift_type_id, date=a.date, is_locked=a.is_locked,
                        source=a.source, note=a.note,
                    )
                    for a in source.assignments.all()
                ],
                batch_size=1000,
            )
        log_action(request.user, "schedule.duplicate", copy, f"Duplicated {source.name} as {copy.name}")
        return Response(
            ScheduleSerializer(copy, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"])
    def compare(self, request):
        """Side-by-side solver statistics: /compare/?ids=1,2,3"""
        ids = [int(i) for i in request.query_params.get("ids", "").split(",") if i.strip().isdigit()]
        if len(ids) < 2:
            return Response({"detail": "Pass at least two ids, e.g. ?ids=1,2"}, status=status.HTTP_400_BAD_REQUEST)
        rows = [
            {"id": s.id, "name": s.name, "status": s.status, "solver_status": s.solver_status, **s.solver_stats}
            for s in self.get_queryset().filter(pk__in=ids)
        ]
        return Response(rows)


class ShiftAssignmentFilter(filters.FilterSet):
    from_date = JalaliDateFilter(field_name="date", lookup_expr="gte")
    to_date = JalaliDateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = ShiftAssignment
        fields = ["schedule", "nurse", "department", "shift_type", "is_locked", "source"]


class ShiftAssignmentViewSet(viewsets.ModelViewSet):
    """Admins: full. Nurses: read their own shifts in published schedules."""

    serializer_class = ShiftAssignmentSerializer
    filterset_class = ShiftAssignmentFilter
    ordering_fields = ["date"]

    def get_queryset(self):
        qs = ShiftAssignment.objects.select_related("nurse__user", "department", "shift_type", "schedule")
        user = self.request.user
        if user.is_scheduler:
            return qs
        return qs.filter(nurse__user=user, schedule__status=Schedule.Status.PUBLISHED)

    def get_permissions(self):
        if self.action in ("list", "retrieve", "my"):
            return [IsAuthenticated()]
        return [IsAdminRole()]

    @action(detail=False, methods=["get"])
    def my(self, request):
        """The logged-in nurse's own shifts (published schedules only)."""
        qs = self.filter_queryset(
            self.get_queryset().filter(nurse__user=request.user, schedule__status=Schedule.Status.PUBLISHED)
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def perform_create(self, serializer):
        assignment = serializer.save(
            source=ShiftAssignment.Source.MANUAL,
            is_locked=serializer.validated_data.get("is_locked", True),  # manual = locked by default
        )
        log_action(self.request.user, "assignment.create", assignment, describe(assignment))
        if assignment.schedule.status == Schedule.Status.PUBLISHED:
            notify([assignment.nurse.user], "A shift was added to your schedule", describe(assignment),
                    kind=Notification.Kind.SCHEDULE, related=assignment)

    def perform_update(self, serializer):
        old_user = serializer.instance.nurse.user
        old_text = describe(serializer.instance)
        assignment = serializer.save()
        log_action(self.request.user, "assignment.update", assignment, f"{old_text} -> {describe(assignment)}")
        if assignment.schedule.status == Schedule.Status.PUBLISHED:
            notify({old_user, assignment.nurse.user}, "Your shift was changed",
                    f"Before: {old_text}. Now: {describe(assignment)} ({assignment.nurse.full_name}).",
                    kind=Notification.Kind.SCHEDULE, related=assignment)

    def perform_destroy(self, instance):
        text, user, published = describe(instance), instance.nurse.user, instance.schedule.status == "published"
        log_action(self.request.user, "assignment.delete", instance, text)
        instance.delete()
        if published:
            notify([user], "A shift was removed from your schedule", text, kind=Notification.Kind.SCHEDULE)


class DemandRuleViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = DemandRule.objects.select_related("department", "shift_type")
    serializer_class = DemandRuleSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["department", "shift_type", "applies_to", "is_active"]


class ShiftShortageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShiftShortage.objects.select_related("department", "shift_type")
    serializer_class = ShiftShortageSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["schedule", "department", "shift_type", "kind"]