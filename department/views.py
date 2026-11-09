from django.shortcuts import render

# Create your views here.
from django_filters import rest_framework as filters
from rest_framework import generics, viewsets

from core.filters import JalaliDateFilter
from core.mixins import ProtectedDeleteMixin
from core.permissions import IsAdminRoleOrReadOnly
from .models import Department, Holiday, ShiftType, Skill, WorkRule
from .serializers import (
    DepartmentSerializer,
    HolidaySerializer,
    ShiftTypeSerializer,
    SkillSerializer,
    WorkRuleSerializer,
)


class DepartmentViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminRoleOrReadOnly]
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]


class SkillViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [IsAdminRoleOrReadOnly]
    search_fields = ["name", "code"]


class ShiftTypeViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = ShiftType.objects.all()
    serializer_class = ShiftTypeSerializer
    permission_classes = [IsAdminRoleOrReadOnly]
    filterset_fields = ["is_active", "is_night"]
    search_fields = ["name", "code"]


class HolidayFilter(filters.FilterSet):
    from_date = JalaliDateFilter(field_name="date", lookup_expr="gte")
    to_date = JalaliDateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Holiday
        fields = ["is_official"]


class HolidayViewSet(viewsets.ModelViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [IsAdminRoleOrReadOnly]
    filterset_class = HolidayFilter
    search_fields = ["title"]


class WorkRuleView(generics.RetrieveUpdateAPIView):

    serializer_class = WorkRuleSerializer
    permission_classes = [IsAdminRoleOrReadOnly]

    def get_object(self):
        return WorkRule.get_solo()