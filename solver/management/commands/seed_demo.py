import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from department.models import Department, ShiftType, Skill
from schedule.models import DemandRule, Schedule
from staff.models import Nurse, NurseSkill

User = get_user_model()

# (department, shift code, min nurses, min experienced, required skill code, skill count)
DEMAND = [
    ("ICU", "DAY", 2, 0, None, 0), ("ICU", "NIGHT", 2, 0, "ICU", 1),
    ("ER", "DAY", 3, 0, None, 0), ("ER", "NIGHT", 2, 1, None, 0),
    ("PED", "DAY", 2, 0, None, 0), ("PED", "NIGHT", 1, 0, None, 0),
    ("SUR", "DAY", 2, 0, None, 0), ("SUR", "NIGHT", 1, 0, None, 0),
]


class Command(BaseCommand):
    help = "Create demo nurses, demand rules and an empty draft schedule."

    def add_arguments(self, parser):
        parser.add_argument("--nurses", type=int, default=40)
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, **opts):
        call_command("seed_department")
        rng = random.Random(42)
        depts = {d.code: d for d in Department.objects.all()}
        skills = {s.code: s for s in Skill.objects.all()}
        pattern = ["ICU"] * 6 + ["ER"] * 6 + ["PED"] * 4 + ["SUR"] * 4
        codes = list(depts)

        for i in range(1, opts["nurses"] + 1):
            code = pattern[(i - 1) % len(pattern)]
            user, created = User.objects.get_or_create(
                username=f"nurse{i:02d}",
                defaults={"first_name": f"Nurse{i:02d}", "last_name": code, "role": User.Role.NURSE},
            )
            if created:
                user.set_password("Nurse12345!")
                user.save()
            nurse, nurse_created = Nurse.objects.get_or_create(
                user=user,
                defaults={
                    "personnel_code": f"N{i:03d}",
                    "home_department": depts[code],
                    "experience_years": rng.choice([0.5, 1, 2, 4, 6, 8, 10]),
                },
            )
            if nurse_created:
                if code == "ICU":
                    NurseSkill.objects.create(nurse=nurse, skill=skills["ICU"], level=rng.choice([1, 2, 3]))
                if i % 5 == 0:   # every 5th nurse can float to another department
                    other = codes[(codes.index(code) + 1) % len(codes)]
                    nurse.allowed_departments.add(depts[other])

        shift_types = {s.code: s for s in ShiftType.objects.all()}
        for dept, shift, total, exp, skill, skill_n in DEMAND:
            DemandRule.objects.update_or_create(
                department=depts[dept], shift_type=shift_types[shift], applies_to=DemandRule.AppliesTo.ALL,
                defaults={"min_nurses": total, "min_experienced": exp,
                            "required_skill": skills[skill] if skill else None, "required_skill_count": skill_n},
            )

        start = timezone.localdate() + timedelta(days=1)
        schedule, _ = Schedule.objects.get_or_create(
            name="Demo schedule",
            defaults={"start_date": start, "end_date": start + timedelta(days=opts["days"] - 1)},
        )
        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Nurses: {opts['nurses']} (password Nurse12345!). Schedule id = {schedule.id}"))
