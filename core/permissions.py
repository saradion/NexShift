from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminRole(BasePermission):
    """Scheduler/admin users only."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_scheduler)


class IsAdminRoleOrReadOnly(BasePermission):

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return request.method in SAFE_METHODS or user.is_scheduler