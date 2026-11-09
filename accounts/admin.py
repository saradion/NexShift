from django.contrib import admin

# Register your models here.

from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active", "is_superuser")
    fieldsets = DjangoUserAdmin.fieldsets + (("SmartShift", {"fields": ("role", "phone")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (("SmartShift", {"fields": ("role", "phone")}),)
