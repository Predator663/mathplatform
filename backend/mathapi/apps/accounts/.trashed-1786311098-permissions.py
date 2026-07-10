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


class TeacherFeatureEnabled(BasePermission):
    """
    Gate a write action behind an admin-configurable toggle
    (SiteSettings.teacher_permissions), on top of the normal role check.

    Super admins always pass. Teachers pass only if the admin has enabled
    `action` for `resource` in Settings (defaults preserve today's
    behaviour — see accounts.models.DEFAULT_TEACHER_PERMISSIONS). Any other
    role is denied outright.

    Also useful for actions that used to be strictly admin-only (e.g.
    subjects): pointing it at a resource whose default is all-False
    reproduces "admin only" until an admin opts teachers in from Settings.

    Usage (inside a get_permissions() method, instantiated manually since
    it needs constructor args):
        return [TeacherFeatureEnabled('students', 'delete')]
    """
    message = 'This feature has been disabled for teachers by an administrator.'

    def __init__(self, resource, action):
        self.resource = resource
        self.action = action

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role == 'super_admin':
            return True
        if user.role != 'teacher':
            return False
        from .models import SiteSettings
        return SiteSettings.get().can_teacher(self.resource, self.action)
