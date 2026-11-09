from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LeaveRequestViewSet, NurseViewSet

router = DefaultRouter()
router.register("nurses", NurseViewSet, basename="nurse")
router.register("leave-requests", LeaveRequestViewSet, basename="leave-request")

urlpatterns = [path("", include(router.urls))]