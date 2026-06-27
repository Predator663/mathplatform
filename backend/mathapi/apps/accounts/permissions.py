"""
Shared permission helpers used across all apps.
"""
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Only super_admin users."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'super_admin')


class IsTeacherOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in ('super_admin', 'teacher')
        )
