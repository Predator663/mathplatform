import csv
import io
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse

from .models import DailyQuiz, DailyQuizScore
from .serializers import (
    DailyQuizSerializer, DailyQuizCreateSerializer,
    DailyQuizScoreSerializer, BulkQuizScoreSerializer,
)
from . import analytics_services
from mathapi.apps.students.models import StudentProfile
from mathapi.apps.accounts.scoping import (
    get_teacher_subjects, get_teacher_classrooms, scope_quizzes, assert_classroom_owned,
)


class DailyQuizViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['classroom', 'subject', 'topic', 'term', 'academic_year']
    search_fields = ['title']
    ordering_fields = ['date', 'title', 'created_at', 'max_score']
    ordering = ['-date']

    def get_permissions(self):
        from mathapi.apps.accounts.permissions import IsTeacherOrAdmin, TeacherFeatureEnabled
        if self.action == 'create':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('quizzes', 'add')]
        if self.action in ['update', 'partial_update']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('quizzes', 'edit')]
        if self.action == 'destroy':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('quizzes', 'delete')]
        if self.action == 'bulk_scores':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('quizzes', 'edit')]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        present_scores = DailyQuizScore.objects.filter(is_absent=False)
        return scope_quizzes(
            self.request.user,
            DailyQuiz.objects.select_related('classroom', 'subject', 'topic', 'created_by')
            .prefetch_related(Prefetch('scores', queryset=present_scores, to_attr='present_scores')),
        )

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DailyQuizCreateSerializer
        return DailyQuizSerializer

    def perform_create(self, serializer):
        # A quiz with no classroom the teacher is actually assigned to would
        # be created successfully but then vanish from scope_quizzes()
        # forever — check ownership up front instead of letting that happen.
        classroom = serializer.validated_data.get('classroom')
        if self.request.user.role == 'teacher' and classroom is not None:
            assert_classroom_owned(self.request.user, classroom.id)
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Soft delete — never hard-delete quizzes (mirrors Exam.destroy)."""
        quiz = self.get_object()
        if request.user.role != 'super_admin' and quiz.created_by != request.user:
            return Response({'detail': 'You can only delete your own quizzes.'}, status=status.HTTP_403_FORBIDDEN)
        quiz.is_deleted = True
        quiz.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def bulk_scores(self, request, pk=None):
        quiz = self.get_object()
        serializer = BulkQuizScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        errors, created, updated = [], [], []
        allowed_students = StudentProfile.objects.filter(
            classroom_id=quiz.classroom_id, is_active=True,
        ).values_list('student_id', flat=True)
        allowed_set = set(allowed_students)

        with transaction.atomic():
            for item in serializer.validated_data['scores']:
                sid = item['student_id']
                if sid not in allowed_set:
                    errors.append({'student_id': sid,
                                   'error': "Student not enrolled in this quiz's classroom."})
                    continue
                try:
                    student = StudentProfile.objects.get(student_id=sid)
                    score_val = float(item['score'])
                    is_absent = item.get('is_absent', False)

                    if not is_absent and score_val > float(quiz.max_score):
                        errors.append({'student_id': sid,
                                       'error': f'Score {score_val} exceeds max {quiz.max_score}'})
                        continue
                    if score_val < 0:
                        errors.append({'student_id': sid, 'error': 'Score cannot be negative.'})
                        continue

                    obj, was_created = DailyQuizScore.objects.update_or_create(
                        quiz=quiz, student=student,
                        defaults={
                            'score': score_val,
                            'is_absent': is_absent,
                            'remarks': item.get('remarks', ''),
                            'entered_by': request.user,
                        }
                    )
                    (created if was_created else updated).append(sid)
                except StudentProfile.DoesNotExist:
                    errors.append({'student_id': sid, 'error': 'Student not found'})

        return Response({
            'created': len(created), 'updated': len(updated), 'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='academic-years')
    def academic_years(self, request):
        years = (
            self.get_queryset()
            .exclude(academic_year='')
            .order_by('-academic_year')
            .values_list('academic_year', flat=True)
            .distinct()
        )
        return Response(list(years))

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        """CSV of the current filtered/searched/sorted quiz list — same
        pattern as ExamViewSet.export_csv."""
        queryset = self.filter_queryset(self.get_queryset())

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Date', 'Title', 'Classroom', 'Subject', 'Topic', 'Term', 'Academic Year',
            'Max Score', 'Passing Score', 'Students Scored', 'Average %', 'Pass Rate %',
            'Created By',
        ])
        for quiz in queryset:
            present_scores = quiz.present_scores if hasattr(quiz, 'present_scores') else list(quiz.scores.filter(is_absent=False))
            score_count = len(present_scores)
            avg = round(sum(float(s.score) for s in present_scores) / float(quiz.max_score) / score_count * 100, 1) if score_count else ''
            passed = [s for s in present_scores if float(s.score) >= float(quiz.passing_score)]
            pass_rate = round(len(passed) / score_count * 100, 1) if score_count else ''
            writer.writerow([
                quiz.date.isoformat(), quiz.display_title, str(quiz.classroom),
                quiz.subject.name if quiz.subject_id else '',
                quiz.topic.name if quiz.topic_id else 'Mixed / Untagged',
                quiz.get_term_display(), quiz.academic_year,
                quiz.max_score, quiz.passing_score, score_count, avg, pass_rate,
                quiz.created_by.get_full_name() if quiz.created_by_id else '',
            ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="daily_quizzes_export.csv"'
        return response


class DailyQuizScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only — score entry goes through DailyQuizViewSet.bulk_scores()
    so every write is validated against the quiz's own classroom roster in
    one place. This exists for querying scores directly (e.g. a single
    student's quiz history) without needing the parent quiz's id first."""
    serializer_class = DailyQuizScoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['quiz', 'student', 'is_absent']
    ordering_fields = ['entered_at', 'score']
    ordering = ['-quiz__date']

    def get_queryset(self):
        scoped_quizzes = scope_quizzes(self.request.user)
        return DailyQuizScore.objects.filter(quiz__in=scoped_quizzes).select_related(
            'quiz', 'quiz__topic', 'student',
        )


def _int_param(request, name):
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


class ClassroomQuizAnalyticsView(APIView):
    """GET /api/quizzes/classroom/<id>/analytics/
    ?subject_id=&term=&academic_year=&topic_id=
    Scoped exactly like the rest of the app: a teacher must be assigned to
    this classroom, and — since scope_quizzes() isolates quizzes by
    created_by for teachers — only sees analytics built from quizzes they
    themselves created here. Admins see every quiz in the classroom."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        from mathapi.apps.accounts.permissions import IsTeacherOrAdmin
        if not IsTeacherOrAdmin().has_permission(request, self):
            return Response({'detail': 'Only teachers and administrators can view quiz analytics.'}, status=status.HTTP_403_FORBIDDEN)
        assert_classroom_owned(request.user, classroom_id)

        created_by_id = request.user.id if request.user.role == 'teacher' else None
        data = analytics_services.get_classroom_quiz_analytics(
            classroom_id,
            subject_id=_int_param(request, 'subject_id'),
            term=request.query_params.get('term') or None,
            academic_year=request.query_params.get('academic_year') or None,
            topic_id=_int_param(request, 'topic_id'),
            created_by_id=created_by_id,
        )
        return Response(data)


class StudentQuizProgressView(APIView):
    """GET /api/quizzes/students/<id>/progress/?subject_id=
    Per-student quiz analytics — topic breakdown + trend + summary, plus
    the quiz-specific streak/badges so a progress page needs just one call.
    Access follows the same rule as the exam-analytics equivalent."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        from mathapi.apps.analytics.views import _check_student_access
        from mathapi.apps.gamification import services as gamification_services

        _check_student_access(request.user, student_id)
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        created_by_id = request.user.id if request.user.role == 'teacher' else None
        data = analytics_services.get_student_quiz_topic_progress(
            student_id, subject_id=_int_param(request, 'subject_id'), created_by_id=created_by_id,
        )
        gamified = gamification_services.get_student_quiz_progress(student)
        from mathapi.apps.gamification.serializers import StudentBadgeSerializer, QuizStreakSerializer
        data['streak'] = QuizStreakSerializer(gamified['streak']).data
        data['badges'] = StudentBadgeSerializer(gamified['badges'], many=True).data
        return Response(data)


class MyQuizProgressView(APIView):
    """GET /api/quizzes/my-progress/ — the current (student) user's own
    quiz analytics + streak + badges, no student_id needed."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        student = getattr(request.user, 'student_profile', None)
        if student is None:
            return Response({'detail': 'This account has no student profile.'}, status=status.HTTP_404_NOT_FOUND)

        from mathapi.apps.gamification import services as gamification_services
        from mathapi.apps.gamification.serializers import StudentBadgeSerializer, QuizStreakSerializer

        data = analytics_services.get_student_quiz_topic_progress(student.id)
        gamified = gamification_services.get_student_quiz_progress(student)
        data['student_id'] = student.id
        data['streak'] = QuizStreakSerializer(gamified['streak']).data
        data['badges'] = StudentBadgeSerializer(gamified['badges'], many=True).data
        return Response(data)


class StudentQuizProgressPDFView(APIView):
    """GET /api/quizzes/students/<id>/progress-report.pdf/
    Professional export: quiz summary, streak, badges, score trend, and
    topic mastery — for a parent/teacher to print or share."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        from mathapi.apps.analytics.views import _check_student_access
        from mathapi.apps.reports.views import _resolve_site_name
        from mathapi.apps.reports.pdf_engine import generate_quiz_progress_pdf
        from mathapi.apps.gamification import services as gamification_services

        _check_student_access(request.user, student_id)
        try:
            student = StudentProfile.objects.select_related('classroom', 'user').get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        created_by_id = request.user.id if request.user.role == 'teacher' else None
        progress = analytics_services.get_student_quiz_topic_progress(
            student_id, subject_id=_int_param(request, 'subject_id'), created_by_id=created_by_id,
        )
        quiz_progress = gamification_services.get_student_quiz_progress(student)
        school_name = _resolve_site_name(request)

        pdf_bytes = generate_quiz_progress_pdf(
            student, progress, quiz_progress['streak'], quiz_progress['badges'],
            school_name=school_name,
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="quiz_progress_{student.student_id}.pdf"'
        return response
