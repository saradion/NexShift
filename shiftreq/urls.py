from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ShiftRequestViewSet

router = DefaultRouter()
router.register("", ShiftRequestViewSet, basename="shift-request")

urlpatterns = [path("", include(router.urls))]