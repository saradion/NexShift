

# Create your models here.
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from core.models import TimeStampedModel
from department.models import Department, ShiftType, Skill
from staff.models import Nurse


class Schedule(TimeStampedModel):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="schedules"
    )
    published_at = models.DateTimeField(null=True, blank=True)

    
    solver_status = models.CharField(max_length=20, blank=True)
    solver_stats = models.JSONField(default=dict, blank=True)
    solved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="schedule_end_after_start"),
        ]

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.name} [{self.status}]"


class DemandRule(TimeStampedModel):
    """How many nurses a department needs in a shift type."""

    class AppliesTo(models.TextChoices):
        ALL = "all", "Every day"
        WORKDAYS = "workdays", "Working days"
        OFF_DAYS = "off_days", "Weekends and holidays"

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="demand_rules")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.PROTECT, related_name="demand_rules")
    applies_to = models.CharField(max_length=10, choices=AppliesTo.choices, default=AppliesTo.ALL)
    min_nurses = models.PositiveSmallIntegerField(default=1)
    min_experienced = models.PositiveSmallIntegerField(default=0)
    required_skill = models.ForeignKey(Skill, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    required_skill_count = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department__name", "shift_type__start_time"]
        constraints = [
            models.UniqueConstraint(fields=["department", "shift_type", "applies_to"], name="uniq_demand_rule"),
            models.CheckConstraint(condition=Q(min_experienced__lte=F("min_nurses")), name="demand_exp_le_total"),
            models.CheckConstraint(condition=Q(required_skill_count__lte=F("min_nurses")), name="demand_skill_le_total"),
        ]

    def __str__(self):
        return f"{self.department} / {self.shift_type.code}: {self.min_nurses}"


class ShiftAssignment(TimeStampedModel):
    class Source(models.TextChoices):
        SOLVER = "solver", "Solver"
        MANUAL = "manual", "Manual"
        SWAP = "swap", "Swap"
        SUBSTITUTE = "substitute", "Substitute"

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="assignments")
    nurse = models.ForeignKey(Nurse, on_delete=models.PROTECT, related_name="assignments")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="assignments")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.PROTECT, related_name="assignments")
    date = models.DateField()
    is_locked = models.BooleanField(default=False, help_text="Locked assignments are kept when the solver re-runs.")
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.MANUAL)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["date", "shift_type_id", "department_id"]
        constraints = [
            models.UniqueConstraint(fields=["schedule", "nurse", "date", "shift_type"], name="uniq_assignment_slot"),
        ]
        indexes = [
            models.Index(fields=["schedule", "date"]),
            models.Index(fields=["nurse", "date"]),
        ]

    def __str__(self):
        return f"{self.date} {self.shift_type.code} {self.nurse.personnel_code} @ {self.department.code}"


class ShiftShortage(TimeStampedModel):
    """A requirement the solver could not fully meet, with a short explanation."""

    class Kind(models.TextChoices):
        HEADCOUNT = "headcount", "Not enough nurses"
        EXPERIENCE = "experience", "Not enough experienced nurses"
        SKILL = "skill", "Not enough nurses with the required skill"

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="shortages")
    date = models.DateField()
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="+")
    shift_type = models.ForeignKey(ShiftType, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    required = models.PositiveSmallIntegerField()
    assigned = models.PositiveSmallIntegerField()
    missing = models.PositiveSmallIntegerField()
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["date", "department_id", "shift_type_id"]