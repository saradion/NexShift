from rest_framework import serializers

from core.serializers import JalaliDateField, JalaliModelSerializer
from schedule.models import Schedule

from .models import ShiftRequest

OPEN = (ShiftRequest.Status.PENDING_PEER, ShiftRequest.Status.PENDING_ADMIN)


class ShiftRequestSerializer(JalaliModelSerializer):
    requester_name = serializers.CharField(source="requester.full_name", read_only=True)
    target_nurse_name = serializers.CharField(source="target_nurse.full_name", read_only=True, allow_null=True)
    assignment_date = JalaliDateField(source="assignment.date", read_only=True)
    assignment_shift = serializers.CharField(source="assignment.shift_type.name", read_only=True)
    assignment_department = serializers.CharField(source="assignment.department.name", read_only=True)

    class Meta:
        model = ShiftRequest
        fields = [
            "id", "request_type", "status", "requester", "requester_name",
            "assignment", "assignment_date", "assignment_shift", "assignment_department",
            "target_nurse", "target_nurse_name", "target_assignment",
            "requested_date", "requested_shift_type", "reason",
            "reviewed_by", "reviewed_at", "admin_note", "created_at",
        ]
        read_only_fields = ["requester", "status", "reviewed_by", "reviewed_at", "admin_note", "created_at"]
        extra_kwargs = {"reason": {"required": True, "allow_blank": False}}

    def validate(self, attrs):
        nurse = getattr(self.context["request"].user, "nurse_profile", None)
        if nurse is None:
            raise serializers.ValidationError("Only nurses can submit shift requests.")

        assignment = attrs["assignment"]
        if assignment.nurse_id != nurse.id:
            raise serializers.ValidationError({"assignment": "You can only submit requests about your own shifts."})
        if assignment.schedule.status != Schedule.Status.PUBLISHED:
            raise serializers.ValidationError({"assignment": "The schedule is not published."})
        if ShiftRequest.objects.filter(requester=nurse, assignment=assignment, status__in=OPEN).exists():
            raise serializers.ValidationError("You already have an open request for this shift.")

        rtype = attrs["request_type"]
        if rtype == ShiftRequest.RequestType.SWAP:
            other = attrs.get("target_assignment")
            target = attrs.get("target_nurse")
            if other is not None:
                if target is not None and target.id != other.nurse_id:
                    raise serializers.ValidationError("target_assignment does not belong to target_nurse.")
                if other.schedule_id != assignment.schedule_id:
                    raise serializers.ValidationError("Both shifts must be in the same schedule.")
                if other.date == assignment.date and other.shift_type_id == assignment.shift_type_id:
                    raise serializers.ValidationError("Swapping two shifts at the same time is not supported.")
                target = other.nurse
            if target is None:
                raise serializers.ValidationError("Choose a colleague (target_nurse) or one of their shifts.")
            if target.id == nurse.id:
                raise serializers.ValidationError("You cannot swap with yourself.")
            attrs["target_nurse"] = target
        else:
            attrs.pop("target_nurse", None)
            attrs.pop("target_assignment", None)
            if rtype == ShiftRequest.RequestType.OBJECTION:
                attrs.pop("requested_date", None)
                attrs.pop("requested_shift_type", None)

        attrs["requester"] = nurse
        return attrs


class ReviewNoteSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)