from django.shortcuts import get_object_or_404
from django.db.models import Count
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend

from .models import LeagueSeason, LeagueGroup, LeagueMembership, PromotionEvent
from .serializers import (
    LeagueSeasonSerializer, LeagueSeasonDetailSerializer, CreateSeasonSerializer,
    LeagueGroupSerializer, LeagueMembershipSerializer, PromotionEventSerializer,
)
from . import services
from mathapi.apps.accounts.permissions import IsTeacherOrAdmin
from mathapi.apps.accounts.scoping import get_teacher_classrooms, assert_classroom_owned, scope_league_seasons


class LeagueSeasonViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['classroom', 'status']

    def get_queryset(self):
        return scope_league_seasons(self.request.user).select_related(
            'classroom', 'baseline_exam', 'created_by',
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LeagueSeasonDetailSerializer
        return LeagueSeasonSerializer

    def create(self, request, *args, **kwargs):
        from mathapi.apps.students.models import Classroom
        from mathapi.apps.exams.models import Exam

        payload = CreateSeasonSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        classroom = get_object_or_404(Classroom, id=data['classroom_id'])
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom.id)
        exam = get_object_or_404(Exam, id=data['baseline_exam_id'])

        try:
            season, unplaced = services.create_season(
                classroom=classroom, baseline_exam=exam, title=data['title'], created_by=request.user,
                interval_mode=data['interval_mode'], band_width=data.get('band_width', 10),
                promotion_mode=data['promotion_mode'], manual_bands=data.get('manual_bands'),
            )
        except ValueError as exc:
            raise ValidationError(str(exc))

        out = LeagueSeasonDetailSerializer(season).data
        out['unplaced'] = [
            {'student_id': u['student'].id, 'student_name': u['student'].full_name, 'reason': u['reason']}
            for u in unplaced
        ]
        return Response(out, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        season = self.get_object()
        if self.request.user.role != 'super_admin' and season.created_by_id != self.request.user.id:
            raise PermissionDenied('You can only edit seasons you created.')
        serializer.save()

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        season = self.get_object()
        season.status = LeagueSeason.Status.ARCHIVED
        season.save(update_fields=['status'])
        return Response(LeagueSeasonSerializer(season).data)

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        season = self.get_object()
        season.status = LeagueSeason.Status.ACTIVE
        season.save(update_fields=['status'])
        return Response(LeagueSeasonSerializer(season).data)

    @action(detail=True, methods=['post'], url_path='evaluate-promotions')
    def evaluate_promotions(self, request, pk=None):
        from mathapi.apps.exams.models import Exam
        season = self.get_object()
        exam_id = request.data.get('trigger_exam_id')
        if not exam_id:
            raise ValidationError('trigger_exam_id is required.')
        exam = get_object_or_404(Exam, id=exam_id)
        summary = services.evaluate_promotions(season, exam)
        summary['newly_awarded_badges'] = {
            k: [{'code': b.code, 'name': b.name, 'icon': b.icon} for b in v]
            for k, v in summary['newly_awarded_badges'].items()
        }
        return Response(summary)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        season = self.get_object()
        return Response(services.get_league_analytics(season))

    @action(detail=True, methods=['post'], url_path='place-student')
    def place_student_action(self, request, pk=None):
        from mathapi.apps.students.models import StudentProfile
        season = self.get_object()
        student = get_object_or_404(StudentProfile, id=request.data.get('student_id'))
        group = get_object_or_404(LeagueGroup, id=request.data.get('group_id'), season=season)
        score = request.data.get('score')
        membership = services.place_student(season, student, group, score=score)
        return Response(LeagueMembershipSerializer(membership).data)


class LeagueGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = LeagueGroupSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['season']

    def get_queryset(self):
        seasons = scope_league_seasons(self.request.user)
        return LeagueGroup.objects.filter(season__in=seasons).annotate(
            member_count=Count('members', distinct=True),
        ).select_related('season').order_by('season', 'order')

    def perform_create(self, serializer):
        season = serializer.validated_data['season']
        if self.request.user.role == 'teacher':
            assert_classroom_owned(self.request.user, season.classroom_id)
        serializer.save()


class PromotionEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = PromotionEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['season', 'status', 'student']

    def get_queryset(self):
        seasons = scope_league_seasons(self.request.user)
        return PromotionEvent.objects.filter(season__in=seasons).select_related(
            'student__user', 'from_group', 'to_group', 'trigger_exam', 'decided_by',
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        event = self.get_object()
        if event.status != PromotionEvent.Status.PENDING:
            return Response({'detail': 'This promotion has already been decided.'}, status=status.HTTP_400_BAD_REQUEST)
        event = services.apply_promotion(event, decided_by=request.user)
        return Response(PromotionEventSerializer(event).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        event = self.get_object()
        if event.status != PromotionEvent.Status.PENDING:
            return Response({'detail': 'This promotion has already been decided.'}, status=status.HTTP_400_BAD_REQUEST)
        event = services.reject_promotion(event, decided_by=request.user)
        return Response(PromotionEventSerializer(event).data)


class HallOfFameView(APIView):
    """GET /api/leagues/hall-of-fame/?classroom=<id>"""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        from mathapi.apps.students.models import Classroom
        classroom = None
        classrooms = None
        classroom_id = request.query_params.get('classroom')
        if classroom_id:
            classroom = get_object_or_404(Classroom, id=classroom_id)
            if request.user.role == 'teacher':
                assert_classroom_owned(request.user, classroom.id)
        elif request.user.role == 'teacher':
            classrooms = get_teacher_classrooms(request.user)
        limit = int(request.query_params.get('limit', 10))
        return Response(services.get_hall_of_fame(classroom=classroom, classrooms=classrooms, limit=limit))


class StudentLeagueSummaryView(APIView):
    """GET /api/leagues/student-summary/<student_id>/ — teacher/admin use
    only (e.g. alongside a student's full analytics view); never surfaced
    on the student's own dashboard."""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request, student_id):
        from mathapi.apps.students.models import StudentProfile
        student = get_object_or_404(StudentProfile, id=student_id)
        return Response(services.get_student_league_summary(student))
