from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets

from core.permissions import IsAdminRole

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["action", "object_type", "object_id", "actor"]
    search_fields = ["summary"]