from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DemandRuleViewSet, ScheduleViewSet, ShiftAssignmentViewSet, ShiftShortageViewSet

router = DefaultRouter()
router.register("schedules", ScheduleViewSet, basename="schedule")
router.register("assignments", ShiftAssignmentViewSet, basename="assignment")
router.register("demand-rules", DemandRuleViewSet, basename="demand-rule")
router.register("shortages", ShiftShortageViewSet, basename="shortage")

urlpatterns = [path("", include(router.urls))]