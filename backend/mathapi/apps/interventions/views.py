from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend

from .models import InterventionProgram, InterventionStage, DEFAULT_STAGE_TEMPLATE
from .serializers import (
    InterventionProgramSerializer, InterventionProgramDetailSerializer, CreateProgramSerializer,
    InterventionStageSerializer, CompleteStageSerializer, SlowLearnerCandidateSerializer,
)
from . import services
from mathapi.apps.accounts.permissions import IsTeacherOrAdmin
from mathapi.apps.accounts.scoping import get_teacher_classrooms, assert_classroom_owned


class InterventionProgramViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTeacherOrAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['classroom', 'status', 'student']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        classrooms = get_teacher_classrooms(self.request.user)
        return InterventionProgram.objects.filter(classroom__in=classrooms).select_related(
            'student__user', 'classroom', 'subject', 'created_by',
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InterventionProgramDetailSerializer
        return InterventionProgramSerializer

    def create(self, request, *args, **kwargs):
        from mathapi.apps.students.models import StudentProfile
        from mathapi.apps.accounts.models import Subject

        payload = CreateProgramSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        student = get_object_or_404(StudentProfile, id=data['student_id'])
        if not student.classroom_id:
            raise ValidationError('This student has no classroom assigned.')
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, student.classroom_id)

        if InterventionProgram.objects.filter(student=student, status=InterventionProgram.Status.ACTIVE).exists():
            raise ValidationError('This student already has an active intervention program.')

        subject = None
        if data.get('subject_id'):
            subject = get_object_or_404(Subject, id=data['subject_id'])

        custom_stages = None
        if data.get('stages'):
            custom_stages = [{'title': s['title'], 'description': s.get('description', '')} for s in data['stages']]

        program = services.create_program(
            student=student, classroom=student.classroom, created_by=request.user, subject=subject,
            trigger_reason=data.get('trigger_reason', ''), custom_stages=custom_stages,
        )
        return Response(InterventionProgramDetailSerializer(program).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def discontinue(self, request, pk=None):
        program = self.get_object()
        program = services.discontinue_program(program, notes=request.data.get('notes', ''))
        return Response(InterventionProgramSerializer(program).data)

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        program = self.get_object()
        return Response(services.get_program_progress(program))


class InterventionStageViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsTeacherOrAdmin]
    serializer_class = InterventionStageSerializer

    def get_queryset(self):
        classrooms = get_teacher_classrooms(self.request.user)
        return InterventionStage.objects.filter(program__classroom__in=classrooms).select_related('program')

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        stage = self.get_object()
        try:
            stage = services.start_stage(stage)
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(InterventionStageSerializer(stage).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        stage = self.get_object()
        payload = CompleteStageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            stage = services.complete_stage(stage, notes=payload.validated_data.get('notes', ''))
        except ValueError as exc:
            raise ValidationError(str(exc))
        return Response(InterventionStageSerializer(stage).data)


class SlowLearnerCandidatesView(APIView):
    """GET /api/interventions/candidates/?classroom=<id>"""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        from mathapi.apps.students.models import Classroom
        classroom_id = request.query_params.get('classroom')
        if not classroom_id:
            raise ValidationError('classroom is required.')
        classroom = get_object_or_404(Classroom, id=classroom_id)
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom.id)
        candidates = services.detect_slow_learners(classroom)
        return Response(SlowLearnerCandidateSerializer(candidates, many=True).data)


class InterventionAnalyticsView(APIView):
    """GET /api/interventions/analytics/?classroom=<id>"""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        from mathapi.apps.students.models import Classroom
        classroom = None
        classroom_id = request.query_params.get('classroom')
        if classroom_id:
            classroom = get_object_or_404(Classroom, id=classroom_id)
            if request.user.role == 'teacher':
                assert_classroom_owned(request.user, classroom.id)
        return Response(services.get_intervention_analytics(classroom=classroom))


class DefaultStageTemplateView(APIView):
    """GET /api/interventions/default-template/ — read-only preview of the
    default 5-stage plan, shown before a teacher opens a program."""
    permission_classes = [IsTeacherOrAdmin]

    def get(self, request):
        return Response(DEFAULT_STAGE_TEMPLATE)
