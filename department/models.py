from django.db import models

# Create your models here.
import datetime as dt
from decimal import Decimal
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from core.models import TimeStampedModel


def default_weekend_days():
    return [4]  # Monday=0 ... Sunday=6 4 is Friday


class Department(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Skill(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ShiftType(TimeStampedModel):
    #Admin defines. Default : 12h work, 24h rest

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    start_time = models.TimeField()
    duration_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("12.00"),
        validators=[MinValueValidator(Decimal("0.5")), MaxValueValidator(Decimal("24"))],
    )
    min_rest_hours_after = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("24.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Minimum rest a nurse must have after finishing this shift.",
    )
    is_night = models.BooleanField(default=False)
    color = models.CharField(max_length=7, default="#013ab6")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}, {self.duration_hours}h)"

    @property
    def end_time(self) -> dt.time:
        base = dt.datetime.combine(dt.date(2000, 1, 1), self.start_time)
        return (base + dt.timedelta(hours=float(self.duration_hours))).time()

    @property
    def crosses_midnight(self) -> bool:
        return self.end_time <= self.start_time

    def starts_at(self, day: dt.date) -> dt.datetime:
        return timezone.make_aware(dt.datetime.combine(day, self.start_time))

    def ends_at(self, day: dt.date) -> dt.datetime:
        return self.starts_at(day) + dt.timedelta(hours=float(self.duration_hours))


class Holiday(TimeStampedModel):
    date = models.DateField(unique=True)
    title = models.CharField(max_length=150)
    is_official = models.BooleanField(default=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} - {self.title}"


class WorkRule(TimeStampedModel):

    standard_monthly_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("176"))
    max_overtime_monthly_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("60"))
    max_consecutive_shifts = models.PositiveSmallIntegerField(default=3)
    max_night_shifts_monthly = models.PositiveSmallIntegerField(default=8)
    max_consecutive_night_shifts = models.PositiveSmallIntegerField(default=2)
    experienced_min_years = models.DecimalField(max_digits=4, decimal_places=1, default=Decimal("3"))
    weekend_weekdays = models.JSONField(default=default_weekend_days)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return 0, {}

    @classmethod
    def get_solo(cls) -> "WorkRule":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Work rules"