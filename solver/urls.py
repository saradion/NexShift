from django.urls import path

from .views import GenerateScheduleView

urlpatterns = [
    path("schedules/<int:schedule_id>/generate/", GenerateScheduleView.as_view(), name="generate-schedule"),
]