from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, HolidayViewSet, ShiftTypeViewSet, SkillViewSet, WorkRuleView

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("skills", SkillViewSet, basename="skill")
router.register("shift-types", ShiftTypeViewSet, basename="shift-type")
router.register("holidays", HolidayViewSet, basename="holiday")

urlpatterns = [
    path("work-rules/", WorkRuleView.as_view(), name="work-rules"),
    path("", include(router.urls)),
]