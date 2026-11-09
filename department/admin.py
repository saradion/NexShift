from django.contrib import admin

# Register your models here.

from core.jalali import to_jalali_str

from .models import Department, Holiday, ShiftType, Skill, WorkRule


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(ShiftType)
class ShiftTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "start_time", "duration_hours", "min_rest_hours_after", "is_night", "is_active")
    list_filter = ("is_night", "is_active")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "date_jalali", "title", "is_official")
    list_filter = ("is_official",)
    search_fields = ("title",)

    @admin.display(description="Date (Jalali)", ordering="date")
    def date_jalali(self, obj):
        return to_jalali_str(obj.date)


@admin.register(WorkRule)
class WorkRuleAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not WorkRule.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
