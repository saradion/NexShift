from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.serializers import UserSerializer
from core.serializers import JalaliModelSerializer
from department.models import Skill, WorkRule

from .models import LeaveRequest, Nurse, NurseSkill

User = get_user_model()
USER_FIELDS = ("username", "password", "first_name", "last_name", "email", "phone")


# nurse read only
class NurseSkillSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = NurseSkill
        fields = ["skill", "skill_name", "level"]


class NurseSerializer(JalaliModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.CharField(read_only=True)
    home_department_name = serializers.CharField(source="home_department.name", read_only=True)
    skills = NurseSkillSerializer(source="nurse_skills", many=True, read_only=True)
    is_experienced = serializers.SerializerMethodField()
    limits = serializers.SerializerMethodField()

    class Meta:
        model = Nurse
        fields = [
            "id", "personnel_code", "user", "full_name", "home_department", "home_department_name",
            "allowed_departments", "skills", "experience_years", "is_experienced", "employment_type",
            "hire_date", "contract_monthly_hours", "max_overtime_monthly_hours", "max_night_shifts_monthly",
            "can_work_nights", "limits", "is_active", "created_at", "updated_at",
        ]

    def _rule(self):
        return self.context.setdefault("work_rule", WorkRule.get_solo())

    def get_is_experienced(self, obj):
        return obj.is_experienced(self._rule())

    def get_limits(self, obj):
        return {k: float(v) for k, v in obj.limits(self._rule()).items()}


# nurse write
class NurseSkillInputSerializer(serializers.Serializer):
    skill = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all())
    level = serializers.ChoiceField(choices=NurseSkill.Level.choices, default=NurseSkill.Level.BASIC)


class NurseWriteSerializer(JalaliModelSerializer):
    username = serializers.CharField(write_only=True, required=False, max_length=150)
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    skill_levels = NurseSkillInputSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Nurse
        fields = [
            "id", "personnel_code", "username", "password", "first_name", "last_name", "email", "phone",
            "home_department", "allowed_departments", "skill_levels", "experience_years", "employment_type",
            "hire_date", "contract_monthly_hours", "max_overtime_monthly_hours", "max_night_shifts_monthly",
            "can_work_nights", "is_active",
        ]

    def validate_skill_levels(self, value):
        ids = [item["skill"].id for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Duplicate skills.")
        return value

    def validate(self, attrs):
        if self.instance is None:
            missing = [f for f in ("username", "password") if f not in attrs]
            if missing:
                raise serializers.ValidationError({f: "This field is required." for f in missing})
            if User.objects.filter(username=attrs["username"]).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
        elif "username" in attrs and attrs["username"] != self.instance.user.username:
            raise serializers.ValidationError({"username": "Username cannot be changed."})
        return attrs

    @staticmethod
    def _set_skills(nurse, skill_levels):
        nurse.nurse_skills.all().delete()
        NurseSkill.objects.bulk_create(
            [NurseSkill(nurse=nurse, skill=i["skill"], level=i["level"]) for i in skill_levels]
        )

    @transaction.atomic
    def create(self, validated_data):
        user_data = {k: validated_data.pop(k) for k in USER_FIELDS if k in validated_data}
        password = user_data.pop("password")
        skill_levels = validated_data.pop("skill_levels", [])
        allowed = validated_data.pop("allowed_departments", [])

        user = User(role=User.Role.NURSE, is_active=validated_data.get("is_active", True), **user_data)
        user.set_password(password)
        user.save()

        nurse = Nurse.objects.create(user=user, **validated_data)
        nurse.allowed_departments.set(allowed)
        self._set_skills(nurse, skill_levels)
        return nurse

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = {k: validated_data.pop(k) for k in USER_FIELDS if k in validated_data}
        user_data.pop("username", None)
        password = user_data.pop("password", None)
        skill_levels = validated_data.pop("skill_levels", None)

        user = instance.user
        for key, value in user_data.items():
            setattr(user, key, value)
        if password:
            user.set_password(password)
        if "is_active" in validated_data:
            user.is_active = validated_data["is_active"]
        user.save()

        instance = super().update(instance, validated_data)
        if skill_levels is not None:
            self._set_skills(instance, skill_levels)
        return instance

    def to_representation(self, instance):
        return NurseSerializer(instance, context=self.context).data


# req
class LeaveRequestSerializer(JalaliModelSerializer):
    nurse = serializers.PrimaryKeyRelatedField(queryset=Nurse.objects.all(), required=False)
    nurse_name = serializers.CharField(source="nurse.full_name", read_only=True)
    days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "nurse", "nurse_name", "leave_type", "start_date", "end_date", "days", "reason",
            "status", "reviewed_by", "reviewed_at", "review_note", "created_at",
        ]
        read_only_fields = ["status", "reviewed_by", "reviewed_at", "review_note", "created_at"]

    def validate(self, attrs):
        user = self.context["request"].user
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))

        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        if user.is_scheduler:
            nurse = attrs.get("nurse") or (self.instance.nurse if self.instance else None)
        else:
            nurse = getattr(user, "nurse_profile", None)
        if nurse is None:
            raise serializers.ValidationError({"nurse": "A nurse is required."})

        if not user.is_scheduler and start and start < timezone.localdate():
            raise serializers.ValidationError({"start_date": "Leave cannot start in the past."})

        overlapping = LeaveRequest.objects.filter(
            nurse=nurse,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end,
            end_date__gte=start,
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)
        if overlapping.exists():
            raise serializers.ValidationError("This period overlaps another pending or approved leave.")

        attrs["nurse"] = nurse
        return attrs


class LeaveReviewSerializer(serializers.Serializer):
    review_note = serializers.CharField(required=False, allow_blank=True)