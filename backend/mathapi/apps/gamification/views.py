from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from mathapi.apps.students.models import StudentProfile
from . import services
from .models import Badge
from .serializers import BadgeSerializer, StudentBadgeSerializer, StudentStreakSerializer


class BadgeCatalogView(generics.ListAPIView):
    """GET /api/gamification/badges/ — the full catalog, so a progress page
    can show locked/unearned badges alongside earned ones. Never paginated
    — it's a small, fixed set (see catalog.py), not a growing list."""
    serializer_class = BadgeSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    queryset = Badge.objects.filter(is_active=True)


def _progress_response(student):
    progress = services.get_student_progress(student)
    return Response({
        'student_id': student.id,
        'student_name': student.full_name,
        'streak': StudentStreakSerializer(progress['streak']).data,
        'badges': StudentBadgeSerializer(progress['badges'], many=True).data,
    })


class MyProgressView(APIView):
    """GET /api/gamification/my-progress/ — the current user's own streak
    + badges. Student accounts only (a teacher/admin/parent has no
    StudentProfile of their own to report on)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        student = getattr(request.user, 'student_profile', None)
        if student is None:
            return Response({'detail': 'This account has no student profile.'}, status=404)
        return _progress_response(student)


class StudentProgressView(APIView):
    """GET /api/gamification/students/<id>/progress/ — a specific
    student's streak + badges, for teachers/admins/parents. Reuses the
    exact same access rule every other per-student analytics endpoint
    enforces."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        from mathapi.apps.analytics.views import _check_student_access
        _check_student_access(request.user, student_id)
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=404)
        return _progress_response(student)
