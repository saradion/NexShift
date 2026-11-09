from django.contrib import admin

# Register your models here.

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "summary")
    list_filter = ("action",)
    search_fields = ("summary",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
