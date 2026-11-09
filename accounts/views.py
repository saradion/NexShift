from django.shortcuts import render

# Create your views here.
from django.contrib.auth import get_user_model
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import ProtectedDeleteMixin
from core.permissions import IsAdminRole

from .serializers import (
    ChangePasswordSerializer,
    MeSerializer,
    SetPasswordSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class UserViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
#user mgm for admin
    queryset = User.objects.all().order_by("username")
    permission_classes = [IsAdminRole]
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["username", "date_joined"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "set_password":
            return SetPasswordSerializer
        return UserSerializer

    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        user = self.get_object()
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
#users own pf

    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)