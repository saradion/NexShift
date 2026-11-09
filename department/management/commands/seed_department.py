from datetime import time
from decimal import Decimal

from django.core.management.base import BaseCommand

from department.models import Department, ShiftType, Skill, WorkRule


class Command(BaseCommand):
    help = "Create default work rules, departments, skills and the 12h Day/Night shift types."

    def handle(self, *args, **options):
        WorkRule.get_solo()

        for code, name in [("ICU", "Intensive Care Unit"), ("ER", "Emergency"),
                        ("PED", "Pediatrics"), ("SUR", "Surgery")]:
            Department.objects.get_or_create(code=code, defaults={"name": name})

        for code, name in [("ICU", "Critical care"), ("VENT", "Ventilator management"),
                        ("TRIAGE", "Triage"), ("CHARGE", "Charge nurse")]:
            Skill.objects.get_or_create(code=code, defaults={"name": name})

        ShiftType.objects.get_or_create(
            code="DAY",
            defaults=dict(name="Day 12h", start_time=time(7, 0), duration_hours=Decimal("12"),
                        min_rest_hours_after=Decimal("24"), is_night=False, color="#eb8704"),
        )
        ShiftType.objects.get_or_create(
            code="NIGHT",
            defaults=dict(name="Night 12h", start_time=time(19, 0), duration_hours=Decimal("12"),
                        min_rest_hours_after=Decimal("24"), is_night=True, color="#1b0cc0"),
        )
        self.stdout.write(self.style.SUCCESS("Seed data created."))
