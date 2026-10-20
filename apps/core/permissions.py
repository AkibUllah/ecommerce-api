from rest_framework.permissions import BasePermission


class IsStaff(BasePermission):
    """Allow access only to staff users (used for operational endpoints)."""

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
