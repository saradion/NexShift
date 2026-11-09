from django.contrib import admin

# Register your models here.
from django.utils import timezone

from core.jalali import to_jalali_str

from .models import LeaveRequest, Nurse, NurseSkill


class NurseSkillInline(admin.TabularInline):
    model = NurseSkill
    extra = 1


@admin.register(Nurse)
class NurseAdmin(admin.ModelAdmin):
    list_display = ("personnel_code", "full_name", "home_department", "employment_type", "experience_years", "is_active")
    list_filter = ("home_department", "employment_type", "is_active", "can_work_nights")
    search_fields = ("personnel_code", "user__first_name", "user__last_name", "user__username")
    list_select_related = ("user", "home_department")
    filter_horizontal = ("allowed_departments",)
    raw_id_fields = ("user",)
    inlines = [NurseSkillInline]


@admin.action(description="Approve selected pending requests")
def approve_selected(modeladmin, request, queryset):
    queryset.filter(status=LeaveRequest.Status.PENDING).update(
        status=LeaveRequest.Status.APPROVED, reviewed_by=request.user, reviewed_at=timezone.now()
    )


@admin.action(description="Reject selected pending requests")
def reject_selected(modeladmin, request, queryset):
    queryset.filter(status=LeaveRequest.Status.PENDING).update(
        status=LeaveRequest.Status.REJECTED, reviewed_by=request.user, reviewed_at=timezone.now()
    )


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("nurse", "leave_type", "start_jalali", "end_jalali", "status")
    list_filter = ("status", "leave_type")
    search_fields = ("nurse__personnel_code", "nurse__user__last_name")
    list_select_related = ("nurse__user",)
    actions = [approve_selected, reject_selected]

    @admin.display(description="Start (Jalali)", ordering="start_date")
    def start_jalali(self, obj):
        return to_jalali_str(obj.start_date)

    @admin.display(description="End (Jalali)", ordering="end_date")
    def end_jalali(self, obj):
        return to_jalali_str(obj.end_date)
