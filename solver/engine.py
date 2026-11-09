"""
The OR-Tools (CP-SAT) engine.
Part A: load_problem()  reads the database into plain Python objects.
Part B: solve()         builds the CP-SAT model and runs it.
"""
import datetime as dt
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from department.models import Holiday, ShiftType, WorkRule
from schedule.models import DemandRule, ShiftAssignment
from staff.models import LeaveRequest, Nurse

# Penalty weights. Bigger = the solver tries harder to avoid it.
W_MISSING_NURSE = 100000     # one missing nurse in a slot
W_MISSING_SPECIAL = 50000    # missing experienced nurse / missing skill
W_OVERTIME_MIN = 1            # per overtime minute
W_FLOAT = 50                  # working outside the home department
W_NIGHT_SPREAD = 500          # gap between most and fewest night shifts in a department
W_OFFDAY_SPREAD = 300         # gap in weekend/holiday shifts
W_HOURS_SPREAD_MIN = 1        # gap in total minutes among full-timers
BIG = 100000


# =====================  Part A: data  =====================
@dataclass
class Demand:
    min_nurses: int
    min_experienced: int
    skill_id: int | None
    skill_count: int


@dataclass
class NurseInfo:
    nurse: Nurse
    departments: set
    skills: set
    experienced: bool
    limits: dict


@dataclass
class Problem:
    schedule: object
    dates: list
    shifts: dict          # shift_type_id -> ShiftType
    demands: dict         # (date, dept_id, shift_id) -> Demand
    leave_days: set       # (nurse_id, date)
    locked: set           # (nurse_id, date, dept_id, shift_id)
    off_days: set         # weekend weekdays + holidays
    nurses: dict          # nurse_id -> NurseInfo


@dataclass
class Solution:
    status: str
    ok: bool
    assignments: list = field(default_factory=list)   # (nurse_id, date, dept_id, shift_id)
    shortages: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def load_problem(schedule) -> Problem:
    rule = WorkRule.get_solo()
    one_day = dt.timedelta(days=1)
    dates = [schedule.start_date + i * one_day for i in range(schedule.days)]
    shifts = {s.id: s for s in ShiftType.objects.filter(is_active=True)}

    holidays = set(Holiday.objects.filter(date__range=(schedule.start_date, schedule.end_date)).values_list("date", flat=True))
    off_days = {d for d in dates if d.weekday() in rule.weekend_weekdays or d in holidays}

    # Demand: a rule for "workdays"/"off_days" beats the "all" rule for the same department+shift.
    by_pair = defaultdict(dict)
    rules = DemandRule.objects.filter(is_active=True, department__is_active=True, shift_type_id__in=list(shifts))
    for r in rules:
        by_pair[(r.department_id, r.shift_type_id)][r.applies_to] = r
    demands = {}
    for (dept_id, shift_id), kinds in by_pair.items():
        for d in dates:
            specific = DemandRule.AppliesTo.OFF_DAYS if d in off_days else DemandRule.AppliesTo.WORKDAYS
            r = kinds.get(specific) or kinds.get(DemandRule.AppliesTo.ALL)
            if r and r.min_nurses > 0:
                demands[(d, dept_id, shift_id)] = Demand(
                    r.min_nurses, r.min_experienced, r.required_skill_id,
                    r.required_skill_count if r.required_skill_id else 0,
                )

    # Approved leave -> blocked days
    leave_days = set()
    leaves = LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED, start_date__lte=schedule.end_date, end_date__gte=schedule.start_date
    )
    for leave in leaves:
        day, last = max(leave.start_date, schedule.start_date), min(leave.end_date, schedule.end_date)
        while day <= last:
            leave_days.add((leave.nurse_id, day))
            day += one_day

    locked = set(
        ShiftAssignment.objects.filter(schedule=schedule, is_locked=True)
        .values_list("nurse_id", "date", "department_id", "shift_type_id")
    )

    nurses = {}
    qs = (
        Nurse.objects.filter(is_active=True, user__is_active=True)
        .select_related("user")
        .prefetch_related("allowed_departments", "nurse_skills")
    )
    for n in qs:
        nurses[n.id] = NurseInfo(
            nurse=n,
            departments=n.eligible_department_ids(),
            skills={ns.skill_id for ns in n.nurse_skills.all()},
            experienced=n.is_experienced(rule),
            limits=n.limits(rule),
        )

    return Problem(schedule, dates, shifts, demands, leave_days, locked, off_days, nurses)


# =====================  Part B: the model  =====================
def _slot_conflicts(problem: Problem) -> dict:
    """
    For each (date, shift) slot, list the later slots that one nurse can NOT also work:
    they overlap it, or start before (end + min rest after this shift).
    """
    slots = []
    for d in problem.dates:
        for s in problem.shifts.values():
            start = dt.datetime.combine(d, s.start_time)
            end = start + dt.timedelta(hours=float(s.duration_hours))
            rest = dt.timedelta(hours=float(s.min_rest_hours_after))
            slots.append((start, end, rest, (d, s.id)))
    slots.sort(key=lambda t: t[0])

    conflicts = defaultdict(list)
    for i, (_, end_i, rest_i, key_i) in enumerate(slots):
        limit = end_i + rest_i
        for start_j, _, _, key_j in slots[i + 1:]:
            if start_j >= limit:
                break                       # slots are sorted, so all later ones are fine too
            conflicts[key_i].append(key_j)
    return conflicts


def _reason(kind, required, missing, candidates):
    got = required - missing
    what = {"headcount": "nurses", "experience": "experienced nurses", "skill": "nurses with the required skill"}[kind]
    base = f"Needs {required} {what}, only {got} could be assigned."
    if candidates < required:
        return (f"{base} Only {candidates} eligible nurse(s) exist for this slot (department, leave, night "
                f"restrictions). Add staff, allow float nurses, or lower the requirement.")
    return (f"{base} {candidates} eligible nurse(s) exist, but they were busy on neighbouring shifts "
            f"(rest rule) or had reached their hour/night limits.")


def solve(problem: Problem, time_limit: int = 30, fairness: bool = True) -> Solution:
    model = cp_model.CpModel()
    info = problem.nurses
    scale = len(problem.dates) / 30                      # monthly limits scaled to the schedule length
    shift_minutes = {sid: int(round(float(s.duration_hours) * 60)) for sid, s in problem.shifts.items()}

    obj_vars, obj_coefs = [], []

    def add_obj(var, coef):
        obj_vars.append(var)
        obj_coefs.append(coef)

    # ---- 1. VARIABLES: x[nurse, date, dept, shift] = 1 if the nurse works there ----
    x = {}
    by_slot = defaultdict(list)           # (date, dept, shift)  -> [(nurse_id, var)]
    by_nurse_slot = defaultdict(list)     # (nurse, date, shift) -> [var, ...]
    nurse_vars = defaultdict(list)        # nurse -> [((date, dept, shift), var)]

    def make_var(nid, key):
        d, dept_id, shift_id = key
        var = model.NewBoolVar(f"x_{nid}_{d.isoformat()}_{dept_id}_{shift_id}")
        x[(nid,) + key] = var
        by_slot[key].append((nid, var))
        by_nurse_slot[(nid, d, shift_id)].append(var)
        nurse_vars[nid].append((key, var))

    nurses_by_dept = defaultdict(list)
    for nid, ni in info.items():
        for dept_id in ni.departments:
            nurses_by_dept[dept_id].append(nid)

    slots = set(problem.demands) | {(d, dep, sh) for (_, d, dep, sh) in problem.locked}
    for key in sorted(slots):
        d, dept_id, shift_id = key
        shift = problem.shifts.get(shift_id)
        if shift is None:
            continue
        for nid in nurses_by_dept.get(dept_id, []):
            is_locked = (nid, d, dept_id, shift_id) in problem.locked
            if not is_locked:
                if (nid, d) in problem.leave_days:                       # hard: leave
                    continue
                if shift.is_night and not info[nid].nurse.can_work_nights:   # hard: no nights
                    continue
            make_var(nid, key)
    for (nid, d, dept_id, shift_id) in problem.locked:       # locked rows the loop above did not create
        if nid in info and shift_id in problem.shifts and (nid, d, dept_id, shift_id) not in x:
            make_var(nid, (d, dept_id, shift_id))
    for lk in problem.locked:                                 # locked = forced to 1
        if lk in x:
            model.Add(x[lk] == 1)

    # ---- 2. HARD: one place at a time + rest rules ----
    for vs in by_nurse_slot.values():
        if len(vs) > 1:
            model.AddAtMostOne(vs)                            # one department per shift

    conflicts = _slot_conflicts(problem)
    present = defaultdict(set)
    for (nid, d, shift_id) in by_nurse_slot:
        present[nid].add((d, shift_id))
    for nid, mine in present.items():
        for a in mine:
            for b in conflicts.get(a, ()):
                if b in mine:                                 # overlap or not enough rest
                    model.AddAtMostOne(by_nurse_slot[(nid,) + a] + by_nurse_slot[(nid,) + b])

    # ---- 3. DEMAND: never overstaff; understaffing is a penalised shortage ----
    locked_count = Counter((d, dep, sh) for (_, d, dep, sh) in problem.locked)
    short_refs = []

    def track(key, kind, needed, vars_, weight, candidates):
        if needed <= 0:
            return
        if vars_:
            missing = model.NewIntVar(0, needed, f"miss_{kind}")
            model.Add(missing + cp_model.LinearExpr.Sum(vars_) >= needed)
            add_obj(missing, weight)
        else:
            missing = needed                                  # nobody can fill it at all
        short_refs.append({"key": key, "kind": kind, "required": needed, "missing": missing, "candidates": candidates})

    for key, dem in problem.demands.items():
        cand = by_slot.get(key, [])
        all_vars = [v for _, v in cand]
        if all_vars:
            model.Add(cp_model.LinearExpr.Sum(all_vars) <= max(dem.min_nurses, locked_count[key]))
        track(key, "headcount", dem.min_nurses, all_vars, W_MISSING_NURSE, len(all_vars))
        exp_vars = [v for nid, v in cand if info[nid].experienced]
        track(key, "experience", dem.min_experienced, exp_vars, W_MISSING_SPECIAL, len(exp_vars))
        if dem.skill_id:
            skill_vars = [v for nid, v in cand if dem.skill_id in info[nid].skills]
            track(key, "skill", dem.skill_count, skill_vars, W_MISSING_SPECIAL, len(skill_vars))

    # ---- 4. PER-NURSE: hour caps, night caps, overtime, home-department preference ----
    groups = defaultdict(lambda: {"nights": [], "off": [], "hours": []})
    std_minutes, night_pool = {}, []
    for nid, items in nurse_vars.items():
        ni = info[nid]
        lim = ni.limits
        std = int(round(float(lim["monthly_hours"]) * 60 * scale))
        cap = int(round((float(lim["monthly_hours"]) + float(lim["max_overtime_hours"])) * 60 * scale))
        std_minutes[nid] = std

        total = cp_model.LinearExpr.WeightedSum([v for _, v in items], [shift_minutes[k[2]] for k, _ in items])
        model.Add(total <= cap)                               # hard: absolute hour cap
        if cap > std:
            overtime = model.NewIntVar(0, cap - std, f"ot_{nid}")
            model.Add(overtime >= total - std)                # soft: overtime is allowed but costly
            add_obj(overtime, W_OVERTIME_MIN)

        night_vs = [v for k, v in items if problem.shifts[k[2]].is_night]
        if night_vs:
            max_nights = int(math.ceil(float(lim["max_night_shifts"]) * scale))
            model.Add(cp_model.LinearExpr.Sum(night_vs) <= max_nights)   # hard: night cap

        for key, var in items:
            if key[1] != ni.nurse.home_department_id:
                add_obj(var, W_FLOAT)                         # soft: prefer the home department

        g = groups[ni.nurse.home_department_id]
        if night_vs and ni.nurse.can_work_nights:
            g["nights"].append(cp_model.LinearExpr.Sum(night_vs))
            night_pool.append(nid)
        off_vs = [v for k, v in items if k[0] in problem.off_days]
        if off_vs:
            g["off"].append(cp_model.LinearExpr.Sum(off_vs))
        if ni.nurse.employment_type == Nurse.EmploymentType.FULL_TIME:
            g["hours"].append(total)

    # ---- 5. FAIRNESS: shrink the gap between the busiest and least busy colleague ----
    def add_spread(exprs, weight):
        if len(exprs) < 2:
            return
        hi, lo = model.NewIntVar(0, BIG, "hi"), model.NewIntVar(0, BIG, "lo")
        for e in exprs:
            model.Add(hi >= e)
            model.Add(lo <= e)
        add_obj(hi, weight)
        add_obj(lo, -weight)

    if fairness:
        for g in groups.values():
            add_spread(g["nights"], W_NIGHT_SPREAD)
            add_spread(g["off"], W_OFFDAY_SPREAD)
            add_spread(g["hours"], W_HOURS_SPREAD_MIN)

    # ---- 6. OBJECTIVE + SOLVE ----
    if obj_vars:
        model.Minimize(cp_model.LinearExpr.WeightedSum(obj_vars, obj_coefs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit)
    status = solver.Solve(model)
    name = solver.StatusName(status)
    wall = round(solver.WallTime(), 2)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return Solution(status=name, ok=False, stats={"solver_status": name, "wall_time_sec": wall})

    # ---- 7. READ THE ANSWER ----
    assigned = [k for k, v in x.items() if solver.Value(v)]
    got_per_slot = Counter((d, dep, sh) for (_, d, dep, sh) in assigned)

    shortages = []
    for ref in short_refs:
        missing = ref["missing"] if isinstance(ref["missing"], int) else solver.Value(ref["missing"])
        if missing > 0:
            d, dept_id, shift_id = ref["key"]
            shortages.append({
                "date": d, "department_id": dept_id, "shift_type_id": shift_id, "kind": ref["kind"],
                "required": ref["required"], "assigned": ref["required"] - missing, "missing": missing,
                "reason": _reason(ref["kind"], ref["required"], missing, ref["candidates"]),
            })

    minutes, nights = defaultdict(int), defaultdict(int)
    float_count = 0
    for (nid, d, dept_id, shift_id) in assigned:
        minutes[nid] += shift_minutes[shift_id]
        if problem.shifts[shift_id].is_night:
            nights[nid] += 1
        if dept_id != info[nid].nurse.home_department_id:
            float_count += 1
    overtime_total = sum(max(0, minutes[n] - std_minutes[n]) for n in minutes)
    night_counts = [nights[n] for n in night_pool]

    stats = {
        "solver_status": name,
        "objective": round(solver.ObjectiveValue(), 1),
        "best_bound": round(solver.BestObjectiveBound(), 1),
        "wall_time_sec": wall,
        "assignments": len(assigned),
        "nurses_available": len(info),
        "nurses_used": len(minutes),
        "missing_headcount": sum(s["missing"] for s in shortages if s["kind"] == "headcount"),
        "missing_experience": sum(s["missing"] for s in shortages if s["kind"] == "experience"),
        "missing_skill": sum(s["missing"] for s in shortages if s["kind"] == "skill"),
        "overtime_hours_total": round(overtime_total / 60, 1),
        "float_assignments": float_count,
        "night_shifts_min": min(night_counts) if night_counts else 0,
        "night_shifts_max": max(night_counts) if night_counts else 0,
    }
    return Solution(status=name, ok=True, assignments=assigned, shortages=shortages, stats=stats)