import csv
import io
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from .models import MathTopic, Exam, ExamScore, ScoreEditLog
from .serializers import (
    MathTopicSerializer, ExamSerializer, ExamCreateSerializer,
    ExamScoreSerializer, ExamScoreCreateSerializer,
    BulkScoreSerializer, ScoreEditLogSerializer,
)
from mathapi.apps.students.models import StudentProfile


class MathTopicViewSet(viewsets.ModelViewSet):
    queryset = MathTopic.objects.all()
    serializer_class = MathTopicSerializer
    permission_classes = [permissions.IsAuthenticated]


class ExamViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['exam_type', 'term', 'academic_year', 'is_published', 'classrooms']
    search_fields = ['title', 'description']
    ordering_fields = ['exam_date', 'title', 'created_at']
    ordering = ['-exam_date']

    def get_queryset(self):
        user = self.request.user
        qs = Exam.objects.prefetch_related('topic_weights__topic', 'classrooms', 'scores')
        if user.role == 'teacher':
            return qs.filter(created_by=user)
        if user.role == 'student':
            try:
                profile = user.student_profile
                return qs.filter(classrooms=profile.classroom, is_published=True)
            except Exception:
                return qs.none()
        if user.role == 'parent':
            try:
                students = user.linked_students.all().values_list('student__classroom', flat=True)
                return qs.filter(classrooms__in=students, is_published=True)
            except Exception:
                return qs.none()
        return qs.all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExamCreateSerializer
        return ExamSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        exam = self.get_object()
        exam.is_published = True
        exam.save()
        return Response({'detail': 'Exam published successfully.'})

    @action(detail=True, methods=['get'])
    def scores(self, request, pk=None):
        exam = self.get_object()
        scores = ExamScore.objects.filter(exam=exam).select_related(
            'student__user', 'entered_by'
        ).prefetch_related('topic_scores__topic')
        serializer = ExamScoreSerializer(scores, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def bulk_scores(self, request, pk=None):
        """Bulk upload scores via JSON list."""
        exam = self.get_object()
        serializer = BulkScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        errors = []
        created = []
        updated = []

        with transaction.atomic():
            for item in serializer.validated_data['scores']:
                try:
                    student = StudentProfile.objects.get(student_id=item['student_id'])
                    score_val = float(item['score'])
                    is_absent = item.get('is_absent', False)

                    if not is_absent and score_val > float(exam.max_score):
                        errors.append({
                            'student_id': item['student_id'],
                            'error': f'Score {score_val} exceeds max {exam.max_score}'
                        })
                        continue

                    obj, was_created = ExamScore.objects.update_or_create(
                        exam=exam,
                        student=student,
                        defaults={
                            'score': score_val,
                            'is_absent': is_absent,
                            'remarks': item.get('remarks', ''),
                            'entered_by': request.user,
                        }
                    )
                    if was_created:
                        created.append(item['student_id'])
                    else:
                        updated.append(item['student_id'])

                except StudentProfile.DoesNotExist:
                    errors.append({'student_id': item['student_id'], 'error': 'Student not found'})

        return Response({
            'created': len(created),
            'updated': len(updated),
            'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_scores_csv(self, request, pk=None):
        """Bulk upload scores via CSV file. Columns: student_id, score, is_absent, remarks"""
        exam = self.get_object()
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        decoded = csv_file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))

        if not reader.fieldnames or 'student_id' not in [f.strip().lower() for f in reader.fieldnames]:
            return Response({'detail': 'CSV must have a student_id column.'}, status=status.HTTP_400_BAD_REQUEST)

        errors = []
        created = []
        updated = []

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                student_id = row.get('student_id', '')
                score_raw = row.get('score', '')
                is_absent = row.get('is_absent', 'false').lower() in ('true', '1', 'yes')

                if not student_id:
                    errors.append({'row': i, 'error': 'student_id missing'})
                    continue

                try:
                    student = StudentProfile.objects.get(student_id=student_id)
                except StudentProfile.DoesNotExist:
                    errors.append({'row': i, 'student_id': student_id, 'error': 'Student not found'})
                    continue

                if not is_absent:
                    try:
                        score_val = float(score_raw)
                    except (ValueError, TypeError):
                        errors.append({'row': i, 'student_id': student_id, 'error': f'Invalid score: {score_raw!r}'})
                        continue
                    if score_val > float(exam.max_score):
                        errors.append({'row': i, 'student_id': student_id, 'error': f'Score {score_val} exceeds max {exam.max_score}'})
                        continue
                else:
                    score_val = 0

                obj, was_created = ExamScore.objects.update_or_create(
                    exam=exam,
                    student=student,
                    defaults={
                        'score': score_val,
                        'is_absent': is_absent,
                        'remarks': row.get('remarks', ''),
                        'entered_by': request.user,
                    }
                )
                if was_created:
                    created.append(student_id)
                else:
                    updated.append(student_id)

        return Response({
            'created': len(created),
            'updated': len(updated),
            'errors_count': len(errors),
            'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def scores_template(self, request, pk=None):
        """Download a pre-filled CSV template with all students for this exam."""
        exam = self.get_object()
        classroom_ids = exam.classrooms.values_list('id', flat=True)
        students = StudentProfile.objects.filter(
            classroom__in=classroom_ids, is_active=True
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['student_id', 'student_name', 'score', 'is_absent', 'remarks'])
        for s in students:
            writer.writerow([s.student_id, s.full_name, '', 'false', ''])

        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="scores_template_{exam.id}.csv"'
        return response

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        exam = self.get_object()
        scores = ExamScore.objects.filter(exam=exam, is_absent=False)
        if not scores.exists():
            return Response({'detail': 'No scores recorded yet.'})

        score_values = [float(s.score) for s in scores]
        max_s = float(exam.max_score)
        percentages = [(s / max_s) * 100 for s in score_values]
        passed = [s for s in score_values if s >= float(exam.passing_score)]

        buckets = {'0-49': 0, '50-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0}
        for p in percentages:
            if p < 50: buckets['0-49'] += 1
            elif p < 60: buckets['50-59'] += 1
            elif p < 70: buckets['60-69'] += 1
            elif p < 80: buckets['70-79'] += 1
            elif p < 90: buckets['80-89'] += 1
            else: buckets['90-100'] += 1

        return Response({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'total_students': len(score_values),
            'absent_count': ExamScore.objects.filter(exam=exam, is_absent=True).count(),
            'average': round(sum(percentages) / len(percentages), 1),
            'highest': round(max(percentages), 1),
            'lowest': round(min(percentages), 1),
            'pass_rate': round((len(passed) / len(score_values)) * 100, 1),
            'distribution': buckets,
        })


class ExamScoreViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['exam', 'student', 'is_absent']
    ordering_fields = ['score', 'entered_at']

    def get_queryset(self):
        user = self.request.user
        qs = ExamScore.objects.select_related(
            'exam', 'student__user', 'entered_by'
        ).prefetch_related('topic_scores__topic')
        if user.role == 'student':
            try:
                return qs.filter(student=user.student_profile)
            except Exception:
                return qs.none()
        if user.role == 'parent':
            students = user.linked_students.values_list('student', flat=True)
            return qs.filter(student__in=students)
        return qs.all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExamScoreCreateSerializer
        return ExamScoreSerializer

    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        score = self.get_object()
        logs = ScoreEditLog.objects.filter(exam_score=score)
        serializer = ScoreEditLogSerializer(logs, many=True)
        return Response(serializer.data)
