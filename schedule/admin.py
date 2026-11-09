

# Register your models here.
from django.contrib import admin

from core.jalali import to_jalali_str

from .models import DemandRule, Schedule, ShiftAssignment, ShiftShortage


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "status", "solver_status")
    list_filter = ("status",)
    search_fields = ("name",)


@admin.register(DemandRule)
class DemandRuleAdmin(admin.ModelAdmin):
    list_display = ("department", "shift_type", "applies_to", "min_nurses", "min_experienced", "required_skill", "is_active")
    list_filter = ("department", "shift_type", "applies_to", "is_active")


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ("schedule", "date", "date_jalali", "shift_type", "department", "nurse", "is_locked", "source")
    list_filter = ("schedule", "department", "shift_type", "is_locked", "source")
    search_fields = ("nurse__personnel_code", "nurse__user__last_name")
    raw_id_fields = ("nurse",)
    list_select_related = ("schedule", "shift_type", "department", "nurse__user")

    @admin.display(description="Date (Jalali)", ordering="date")
    def date_jalali(self, obj):
        return to_jalali_str(obj.date)


@admin.register(ShiftShortage)
class ShiftShortageAdmin(admin.ModelAdmin):
    list_display = ("schedule", "date", "department", "shift_type", "kind", "required", "missing")
    list_filter = ("schedule", "kind")
