from django.db import models

# Create your models here.
from django.conf import settings
from django.db.models import F, Q
from core.models import TimeStampedModel
from department.models import Department, Skill, WorkRule


class Nurse(TimeStampedModel):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full time"
        PART_TIME = "part_time", "Part time"
        CONTRACT = "contract", "Contract"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nurse_profile")
    personnel_code = models.CharField(max_length=30, unique=True)
    home_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="home_nurses")
    allowed_departments = models.ManyToManyField(
        Department, blank=True, related_name="float_nurses",
        help_text="Extra departments this nurse may work in, besides the home department.",
    )
    skills = models.ManyToManyField(Skill, through="NurseSkill", blank=True, related_name="nurses")

    experience_years = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    employment_type = models.CharField(max_length=12, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    hire_date = models.DateField(null=True, blank=True)

    #null is default work rules
    contract_monthly_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_overtime_monthly_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_night_shifts_monthly = models.PositiveSmallIntegerField(null=True, blank=True)
    can_work_nights = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["personnel_code"]

    def __str__(self):
        return f"{self.personnel_code} - {self.full_name}"

    @property
    def full_name(self) -> str:
        return self.user.get_full_name() or self.user.username

    def eligible_department_ids(self) -> set:
        ids = {self.home_department_id}
        ids.update(d.id for d in self.allowed_departments.all())
        return ids

    def is_experienced(self, rule: WorkRule | None = None) -> bool:
        rule = rule or WorkRule.get_solo()
        return self.experience_years >= rule.experienced_min_years

    def limits(self, rule: WorkRule | None = None) -> dict:
        
        rule = rule or WorkRule.get_solo()
        return {
            "monthly_hours": self.contract_monthly_hours
            if self.contract_monthly_hours is not None else rule.standard_monthly_hours,
            "max_overtime_hours": self.max_overtime_monthly_hours
            if self.max_overtime_monthly_hours is not None else rule.max_overtime_monthly_hours,
            "max_night_shifts": self.max_night_shifts_monthly
            if self.max_night_shifts_monthly is not None else rule.max_night_shifts_monthly,
            "max_consecutive_shifts": rule.max_consecutive_shifts,
            "max_consecutive_night_shifts": rule.max_consecutive_night_shifts,
        }


class NurseSkill(models.Model):
    class Level(models.IntegerChoices):
        BASIC = 1, "Basic"
        INTERMEDIATE = 2, "Intermediate"
        EXPERT = 3, "Expert"

    nurse = models.ForeignKey(Nurse, on_delete=models.CASCADE, related_name="nurse_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="nurse_skills")
    level = models.PositiveSmallIntegerField(choices=Level.choices, default=Level.BASIC)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["nurse", "skill"], name="uniq_nurse_skill")]

    def __str__(self):
        return f"{self.nurse} / {self.skill} ({self.get_level_display()})"


class LeaveRequest(TimeStampedModel):
    class LeaveType(models.TextChoices):
        ANNUAL = "annual", "Annual"
        SICK = "sick", "Sick"
        UNPAID = "unpaid", "Unpaid"
        MATERNITY = "maternity", "Maternity"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    nurse = models.ForeignKey(Nurse, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=12, choices=LeaveType.choices, default=LeaveType.ANNUAL)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_leaves"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="leave_end_after_start"),
        ]

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def __str__(self):
        return f"{self.nurse} {self.start_date} → {self.end_date} [{self.status}]"