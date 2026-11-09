from django.contrib import admin

# Register your models here.

from .models import ShiftRequest


@admin.register(ShiftRequest)
class ShiftRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "request_type", "requester", "assignment", "status", "created_at")
    list_filter = ("request_type", "status")
    search_fields = ("requester__personnel_code", "reason")
    raw_id_fields = ("requester", "assignment", "target_nurse", "target_assignment")
