from django.db import transaction
from django.utils import timezone

from audit.services import log_action
from core.jalali import to_jalali_str
from notif.models import Notification
from notif.services import notify_admins
from schedule.models import ShiftAssignment, ShiftShortage

from .engine import load_problem, solve

FAILURE_MESSAGES = {
    "INFEASIBLE": "No valid schedule exists. Locked assignments probably conflict with each other or with the "
                "rest/hour/night limits. Unlock or remove some and try again.",
    "UNKNOWN": "No solution was found within the time limit. Increase time_limit_seconds and try again.",
    "MODEL_INVALID": "The model was invalid. Please report this with your demand rules.",
}


def generate_schedule(schedule, time_limit=30, fairness=True, user=None) -> dict:
    problem = load_problem(schedule)
    solution = solve(problem, time_limit, fairness)

    schedule.solver_status = solution.status
    schedule.solver_stats = solution.stats
    schedule.solved_at = timezone.now()

    if not solution.ok:
        schedule.save(update_fields=["solver_status", "solver_stats", "solved_at", "updated_at"])
        return {
            "ok": False, "status": solution.status,
            "message": FAILURE_MESSAGES.get(solution.status, "The solver failed."),
            "stats": solution.stats,
        }

    with transaction.atomic():
        # Keep locked assignments, replace everything else.
        schedule.assignments.filter(is_locked=False).delete()
        schedule.shortages.all().delete()
        ShiftAssignment.objects.bulk_create(
            [
                ShiftAssignment(
                    schedule=schedule, nurse_id=nid, date=d, department_id=dep, shift_type_id=sh,
                    source=ShiftAssignment.Source.SOLVER,
                )
                for (nid, d, dep, sh) in solution.assignments
                if (nid, d, dep, sh) not in problem.locked
            ],
            batch_size=1000,
        )
        ShiftShortage.objects.bulk_create(
            [
                ShiftShortage(
                    schedule=schedule, date=s["date"], department_id=s["department_id"],
                    shift_type_id=s["shift_type_id"], kind=s["kind"], required=s["required"],
                    assigned=s["assigned"], missing=s["missing"], reason=s["reason"],
                )
                for s in solution.shortages
            ]
        )
        schedule.save(update_fields=["solver_status", "solver_stats", "solved_at", "updated_at"])

    log_action(user, "schedule.generate", schedule,
                f"Generated {schedule.name}: {solution.stats['assignments']} assignments, "
                f"{len(solution.shortages)} shortages", data=solution.stats)
    notify_admins("Schedule generated",
                    f"{schedule.name}: {solution.stats['assignments']} assignments, "
                    f"{len(solution.shortages)} unfilled requirement(s).",
                    kind=Notification.Kind.SCHEDULE, related=schedule)

    return {
        "ok": True,
        "status": solution.status,           # OPTIMAL = proven best, FEASIBLE = good, stopped at time limit
        "message": f"Generated {solution.stats['assignments']} assignments with {len(solution.shortages)} shortage(s).",
        "stats": solution.stats,
        "shortage_preview": [
            {"date": to_jalali_str(s["date"]), "kind": s["kind"], "missing": s["missing"], "reason": s["reason"]}
            for s in solution.shortages[:5]
        ],
    }