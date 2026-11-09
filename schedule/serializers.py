from rest_framework import serializers

from core.serializers import JalaliModelSerializer

from .models import DemandRule, Schedule, ShiftAssignment, ShiftShortage
from .services import placement_errors


class ScheduleSerializer(JalaliModelSerializer):
    assignment_count = serializers.IntegerField(read_only=True)
    shortage_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Schedule
        fields = [
            "id", "name", "description", "start_date", "end_date", "status", "created_by", "published_at",
            "solver_status", "solver_stats", "solved_at", "assignment_count", "shortage_count", "created_at",
        ]
        read_only_fields = [
            "status", "created_by", "published_at", "solver_status", "solver_stats", "solved_at", "created_at",
        ]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end:
            if end < start:
                raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
            if (end - start).days > 92:
                raise serializers.ValidationError("A schedule can cover at most 93 days.")
        return attrs


class DemandRuleSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    shift_type_name = serializers.CharField(source="shift_type.name", read_only=True)

    class Meta:
        model = DemandRule
        fields = [
            "id", "department", "department_name", "shift_type", "shift_type_name", "applies_to",
            "min_nurses", "min_experienced", "required_skill", "required_skill_count", "is_active",
        ]

    def validate(self, attrs):
        inst = self.instance
        total = attrs.get("min_nurses", inst.min_nurses if inst else 1)
        exp = attrs.get("min_experienced", inst.min_experienced if inst else 0)
        skill = attrs.get("required_skill", inst.required_skill if inst else None)
        skill_n = attrs.get("required_skill_count", inst.required_skill_count if inst else 0)
        if exp > total:
            raise serializers.ValidationError({"min_experienced": "Cannot exceed min_nurses."})
        if skill_n > total:
            raise serializers.ValidationError({"required_skill_count": "Cannot exceed min_nurses."})
        if skill_n and skill is None:
            raise serializers.ValidationError({"required_skill": "Choose the required skill."})
        return attrs


PLACEMENT_FIELDS = ("schedule", "nurse", "department", "shift_type", "date")


class ShiftAssignmentSerializer(JalaliModelSerializer):
    nurse_name = serializers.CharField(source="nurse.full_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    shift_type_name = serializers.CharField(source="shift_type.name", read_only=True)

    class Meta:
        model = ShiftAssignment
        fields = [
            "id", "schedule", "nurse", "nurse_name", "department", "department_name",
            "shift_type", "shift_type_name", "date", "is_locked", "source", "note",
        ]
        read_only_fields = ["source"]
        extra_kwargs = {"is_locked": {"required": False}}

    def validate(self, attrs):
        inst = self.instance
        if inst and "schedule" in attrs and attrs["schedule"] != inst.schedule:
            raise serializers.ValidationError({"schedule": "An assignment cannot be moved to another schedule."})
        if inst and not any(f in attrs for f in PLACEMENT_FIELDS):
            return attrs

        def pick(name):
            return attrs[name] if name in attrs else getattr(inst, name)

        schedule = pick("schedule")
        if schedule.status == Schedule.Status.ARCHIVED:
            raise serializers.ValidationError("Archived schedules cannot be changed.")
        errors = placement_errors(
            schedule, pick("nurse"), pick("department"), pick("date"), pick("shift_type"),
            exclude_pks=[inst.pk] if inst else [],
        )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ShiftShortageSerializer(JalaliModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    shift_type_name = serializers.CharField(source="shift_type.name", read_only=True)

    class Meta:
        model = ShiftShortage
        fields = [
            "id", "schedule", "date", "department", "department_name", "shift_type", "shift_type_name",
            "kind", "required", "assigned", "missing", "reason",
        ]