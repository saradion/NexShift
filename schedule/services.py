import datetime as dt

from core.jalali import to_jalali_str
from staff.models import LeaveRequest

from .models import ShiftAssignment


def _interval(date, shift_type):
    start = dt.datetime.combine(date, shift_type.start_time)
    return start, start + dt.timedelta(hours=float(shift_type.duration_hours))


def placement_errors(schedule, nurse, department, date, shift_type, exclude_pks=()):
    """Return a list of human-readable problems if `nurse` were placed in this slot. Empty list = OK."""
    errors = []

    if not (schedule.start_date <= date <= schedule.end_date):
        errors.append("The date is outside this schedule's period.")
    if not nurse.is_active or not nurse.user.is_active:
        errors.append(f"{nurse.full_name} is not active.")
    if department.id not in nurse.eligible_department_ids():
        errors.append(f"{nurse.full_name} is not allowed to work in {department.name}.")
    if shift_type.is_night and not nurse.can_work_nights:
        errors.append(f"{nurse.full_name} cannot work night shifts.")
    if LeaveRequest.objects.filter(
        nurse=nurse, status=LeaveRequest.Status.APPROVED, start_date__lte=date, end_date__gte=date
    ).exists():
        errors.append(f"{nurse.full_name} is on approved leave on {to_jalali_str(date)}.")

    start, end = _interval(date, shift_type)
    window = dt.timedelta(days=3)
    others = (
        ShiftAssignment.objects.filter(schedule=schedule, nurse=nurse, date__range=(date - window, date + window))
        .exclude(pk__in=list(exclude_pks))
        .select_related("shift_type")
    )
    for other in others:
        o_start, o_end = _interval(other.date, other.shift_type)
        label = f"{to_jalali_str(other.date)} {other.shift_type.name}"
        if o_start < end and start < o_end:
            errors.append(f"{nurse.full_name} already has an overlapping shift ({label}).")
        elif o_end <= start and (start - o_end) < dt.timedelta(hours=float(other.shift_type.min_rest_hours_after)):
            errors.append(f"Not enough rest after the shift on {label}.")
        elif end <= o_start and (o_start - end) < dt.timedelta(hours=float(shift_type.min_rest_hours_after)):
            errors.append(f"Not enough rest before the shift on {label}.")
    return errors