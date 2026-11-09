from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response


class ProtectedDeleteMixin:
# when an object is deleted returns 409 instead of 500
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This object is referenced by other records and cannot be deleted. Deactivate it instead."},
                status=status.HTTP_409_CONFLICT,
            )