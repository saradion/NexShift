from django.shortcuts import render

# Create your views here.
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminRole
from schedule.models import Schedule

from .serializers import GenerateOptionsSerializer
from .services import generate_schedule


class GenerateScheduleView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(request=GenerateOptionsSerializer)
    def post(self, request, schedule_id):
        schedule = get_object_or_404(Schedule, pk=schedule_id)
        if schedule.status != Schedule.Status.DRAFT:
            return Response({"detail": "Only draft schedules can be generated. Duplicate it to try a new scenario."},
                            status=status.HTTP_409_CONFLICT)
        options = GenerateOptionsSerializer(data=request.data)
        options.is_valid(raise_exception=True)
        result = generate_schedule(
            schedule,
            time_limit=options.validated_data["time_limit_seconds"],
            fairness=options.validated_data["fairness"],
            user=request.user,
        )
        return Response(result, status=status.HTTP_200_OK if result["ok"] else status.HTTP_422_UNPROCESSABLE_ENTITY)