from rest_framework import serializers

from core.serializers import JalaliModelSerializer

from .models import Department, Holiday, ShiftType, Skill, WorkRule


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code", "description", "is_active"]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "code", "description"]


class ShiftTypeSerializer(serializers.ModelSerializer):
    end_time = serializers.TimeField(read_only=True)
    crosses_midnight = serializers.BooleanField(read_only=True)

    class Meta:
        model = ShiftType
        fields = [
            "id", "name", "code", "start_time", "duration_hours", "end_time",
            "crosses_midnight", "min_rest_hours_after", "is_night", "color", "is_active",
        ]


class HolidaySerializer(JalaliModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "title", "is_official"]


class WorkRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkRule
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_weekend_weekdays(self, value):
        if not isinstance(value, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in value):
            raise serializers.ValidationError("Must be a list of integers 0-6 (Monday=0 ... Sunday=6).")
        if len(set(value)) != len(value):
            raise serializers.ValidationError("Duplicate weekdays.")
        return value