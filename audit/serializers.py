from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_name", "action", "object_type", "object_id", "summary", "data", "created_at"]

    def get_actor_name(self, obj):
        return str(obj.actor) if obj.actor else "system"