from schedule.models import Schedule, ShiftAssignment
from schedule.services import placement_errors

from .models import ShiftRequest


def apply_request(req: ShiftRequest) -> list:
    """
    Validate and perform an approved request.
    Returns [] on success. Otherwise returns the problems found, and nothing has been changed.
    """
    a = req.assignment
    schedule = a.schedule
    if schedule.status != Schedule.Status.PUBLISHED:
        return ["The schedule is no longer published."]

    if req.request_type == ShiftRequest.RequestType.OBJECTION:
        return []  # nothing to change automatically; the scheduler handles it

    if req.request_type == ShiftRequest.RequestType.CHANGE:
        if req.requested_date is None and req.requested_shift_type_id is None:
            return []  # free-text request; scheduler edits the shift manually
        new_date = req.requested_date or a.date
        new_shift = req.requested_shift_type or a.shift_type
        errors = placement_errors(schedule, a.nurse, a.department, new_date, new_shift, exclude_pks=[a.pk])
        if errors:
            return errors
        a.date, a.shift_type = new_date, new_shift
        a.save(update_fields=["date", "shift_type", "updated_at"])
        return []

    # SWAP
    target, other, requester = req.target_nurse, req.target_assignment, a.nurse
    if target is None:
        return ["The colleague no longer exists."]
    if other is not None:
        errors = placement_errors(schedule, target, a.department, a.date, a.shift_type, [a.pk, other.pk])
        errors += placement_errors(schedule, requester, other.department, other.date, other.shift_type, [a.pk, other.pk])
        if errors:
            return errors
        a.nurse, other.nurse = target, requester
        a.source = other.source = ShiftAssignment.Source.SWAP
        a.save(update_fields=["nurse", "source", "updated_at"])
        other.save(update_fields=["nurse", "source", "updated_at"])
    else:
        errors = placement_errors(schedule, target, a.department, a.date, a.shift_type, [a.pk])
        if errors:
            return errors
        a.nurse, a.source = target, ShiftAssignment.Source.SWAP
        a.save(update_fields=["nurse", "source", "updated_at"])
    return []