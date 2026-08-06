import csv
import io
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction, IntegrityError
from .models import MathTopic, Exam, ExamScore, ScoreEditLog
from .serializers import (
    MathTopicSerializer, ExamSerializer, ExamCreateSerializer,
    ExamScoreSerializer, ExamScoreCreateSerializer,
    BulkScoreSerializer, ScoreEditLogSerializer,
)
from mathapi.apps.students.models import StudentProfile
from mathapi.apps.accounts.scoping import (
    get_teacher_subjects, get_teacher_classrooms, scope_exams,
)


class MathTopicViewSet(viewsets.ModelViewSet):
    serializer_class = MathTopicSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['subject', 'is_active']
    search_fields = ['name']

    def get_queryset(self):
        user = self.request.user
        qs = MathTopic.objects.select_related('subject').filter(is_active=True)
        if user.role == 'super_admin':
            return qs
        # Teachers see only topics for their assigned subjects
        return qs.filter(subject__in=get_teacher_subjects(user))

    def get_permissions(self):
        from mathapi.apps.accounts.permissions import IsAdminRole
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]


class ExamViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['exam_type', 'term', 'academic_year', 'is_published', 'classrooms', 'subject']
    search_fields = ['title', 'description']
    ordering_fields = ['exam_date', 'title', 'created_at']
    ordering = ['-exam_date']

    def get_permissions(self):
        # SECURITY FIX: this previously had no role-based gating at all for
        # create/update/partial_update/bulk_scores/bulk_scores_csv — only
        # class-level IsAuthenticated. get_queryset() scopes *reads*, but
        # DRF doesn't consult get_queryset() for create(), and a student or
        # parent's get_queryset() legitimately includes published exams in
        # their own classroom — so update()/bulk_scores() on those exams
        # was reachable by students/parents too. Now every write action
        # requires teacher/admin, with TeacherFeatureEnabled additionally
        # letting an admin toggle add/edit/delete off for teachers in
        # Settings. destroy() keeps its own extra "only your own exam"
        # check below (admins bypass it).
        from mathapi.apps.accounts.permissions import IsAdminRole, IsTeacherOrAdmin, TeacherFeatureEnabled
        if self.action == 'create':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'add')]
        if self.action in ['update', 'partial_update']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'edit')]
        if self.action == 'destroy':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'delete')]
        if self.action in ['bulk_scores', 'bulk_scores_csv']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'edit')]
        # Trash/restore/empty-trash expose soft-deleted rows that
        # scope_exams() otherwise hides from everyone — admin-only.
        if self.action in ['trash', 'restore', 'empty_trash']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        from django.db.models import Prefetch
        from mathapi.apps.students.models import Classroom
        present_scores = ExamScore.objects.filter(is_absent=False)
        # select_related('grade_level') on the classrooms prefetch avoids an
        # N+1 query per exam when the serializer's classroom_details field
        # reads classroom.grade_level.short_name for each classroom.
        classrooms_qs = Classroom.objects.select_related('grade_level')
        return scope_exams(
            self.request.user,
            Exam.objects.prefetch_related(
                'topic_weights__topic',
                Prefetch('classrooms', queryset=classrooms_qs),
                Prefetch('scores', queryset=present_scores, to_attr='present_scores'),
            ).select_related('subject', 'created_by'),
        )

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExamCreateSerializer
        return ExamSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Soft delete — never hard-delete exams."""
        exam = self.get_object()
        if request.user.role != 'super_admin' and exam.created_by != request.user:
            return Response({'detail': 'You can only delete your own exams.'}, status=status.HTTP_403_FORBIDDEN)
        exam.is_deleted = True
        exam.save(update_fields=['is_deleted'])
        try:
            from mathapi.apps.accounts.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.DELETE,
                model_name='Exam',
                object_id=str(exam.id),
                description=f'Soft-deleted exam: {exam.title}',
            )
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='trash')
    def trash(self, request):
        """Admin-only: every soft-deleted exam, across every teacher.
        Bypasses scope_exams()/get_queryset() by design — this is the one
        place deleted rows are meant to become visible again, so admins can
        see what's sitting in the trash before permanently clearing it."""
        from django.db.models import Prefetch
        from mathapi.apps.students.models import Classroom
        present_scores = ExamScore.objects.filter(is_absent=False)
        classrooms_qs = Classroom.objects.select_related('grade_level')
        qs = (
            Exam.objects
            .filter(is_deleted=True)
            .select_related('subject', 'created_by')
            .prefetch_related(
                Prefetch('classrooms', queryset=classrooms_qs),
                Prefetch('scores', queryset=present_scores, to_attr='present_scores'),
            )
            .order_by('-updated_at')
        )
        serializer = ExamSerializer(qs, many=True)
        return Response({'results': serializer.data, 'count': qs.count()})

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        """Admin-only: un-delete a single exam. Looks the row up directly
        (not via get_object()) since the normal scoped queryset excludes
        soft-deleted exams by definition."""
        try:
            exam = Exam.objects.get(pk=pk, is_deleted=True)
        except Exam.DoesNotExist:
            return Response({'detail': 'Deleted exam not found.'}, status=status.HTTP_404_NOT_FOUND)
        exam.is_deleted = False
        exam.save(update_fields=['is_deleted'])
        try:
            from mathapi.apps.accounts.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.UPDATE,
                model_name='Exam',
                object_id=str(exam.id),
                description=f'Restored soft-deleted exam: {exam.title}',
            )
        except Exception:
            pass
        return Response(ExamSerializer(exam).data)

    @action(detail=False, methods=['post'], url_path='trash/empty')
    def empty_trash(self, request):
        """Admin-only: permanently and irreversibly delete every currently
        soft-deleted exam in one call. Cascades to their topic weights,
        scores, and score-edit logs (all CASCADE FKs onto Exam/ExamScore).
        Requires {"confirm": true} in the body so this can't be triggered
        by an accidental click or a stray script call."""
        if not request.data.get('confirm'):
            return Response(
                {'detail': 'Pass {"confirm": true} to permanently delete all trashed exams.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted_qs = Exam.objects.filter(is_deleted=True)
        count = deleted_qs.count()
        if count == 0:
            return Response({'detail': 'Trash is already empty.', 'deleted_count': 0})
        # Cap how many titles we log — a very large trash shouldn't blow
        # out the audit log description field.
        titles = list(deleted_qs.order_by('title').values_list('title', flat=True)[:20])
        summary = ', '.join(titles) + ('…' if count > len(titles) else '')
        deleted_qs.delete()
        try:
            from mathapi.apps.accounts.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.DELETE,
                model_name='Exam',
                object_id='bulk',
                description=f'Permanently deleted {count} trashed exam(s): {summary}',
            )
        except Exception:
            pass
        return Response({'detail': f'Permanently deleted {count} exam(s).', 'deleted_count': count})

    @action(detail=False, methods=['get'], url_path='pending-review')
    def pending_review(self, request):
        """Admin-only: all unpublished exams awaiting approval, across all teachers.
        Bypasses the normal scope_exams() scoping so admins see every teacher's
        drafts in one place regardless of subject filter."""
        from mathapi.apps.accounts.permissions import IsAdminRole
        if request.user.role != 'super_admin':
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        from django.db.models import Prefetch
        from mathapi.apps.students.models import Classroom
        classrooms_qs = Classroom.objects.select_related('grade_level')
        qs = (
            Exam.objects
            .filter(is_published=False, is_deleted=False)
            .prefetch_related(Prefetch('classrooms', queryset=classrooms_qs), 'topic_weights__topic')
            .select_related('subject', 'created_by')
            .order_by('-created_at')
        )
        serializer = ExamSerializer(qs, many=True)
        return Response({'results': serializer.data, 'count': qs.count()})

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        from mathapi.apps.accounts.permissions import IsAdminRole
        exam = self.get_object()
        # Only admins can publish — teachers submit exams (draft) for review,
        # but only admin approves/publishes them.
        if request.user.role != 'super_admin':
            return Response(
                {'detail': 'Only an administrator can publish exams.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        exam.is_published = True
        exam.save(update_fields=['is_published'])

        # Email notifications are best-effort — a bad SMTP config or a
        # transient failure should never prevent the exam from publishing.
        try:
            from mathapi.apps.notifications.services import notify_exam_published
            notify_exam_published(exam)
        except Exception:
            pass

        return Response({'detail': 'Exam published successfully.'})

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        exam = self.get_object()
        if request.user.role != 'super_admin':
            return Response(
                {'detail': 'Only an administrator can unpublish exams.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        exam.is_published = False
        exam.save(update_fields=['is_published'])
        return Response({'detail': 'Exam moved back to draft.'})

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
        exam = self.get_object()
        serializer = BulkScoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        errors, created, updated = [], [], []

        # Only students enrolled in this exam's classrooms may receive scores.
        # Without this guard a teacher (or anyone who can reach this action)
        # could enter a score for any student_id in the school.
        exam_classroom_ids = exam.classrooms.values_list('id', flat=True)
        allowed_students = StudentProfile.objects.filter(
            classroom__in=exam_classroom_ids, is_active=True,
        ).values_list('student_id', flat=True)
        allowed_set = set(allowed_students)

        with transaction.atomic():
            for item in serializer.validated_data['scores']:
                sid = item['student_id']
                if sid not in allowed_set:
                    errors.append({'student_id': sid,
                                   'error': 'Student not enrolled in this exam\'s classrooms.'})
                    continue
                try:
                    student = StudentProfile.objects.get(student_id=sid)
                    score_val = float(item['score'])
                    is_absent = item.get('is_absent', False)

                    if not is_absent and score_val > float(exam.max_score):
                        errors.append({'student_id': sid,
                                       'error': f'Score {score_val} exceeds max {exam.max_score}'})
                        continue

                    obj, was_created = ExamScore.objects.update_or_create(
                        exam=exam, student=student,
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

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def bulk_scores_csv(self, request, pk=None):
        exam = self.get_object()
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        decoded = csv_file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded))

        if not reader.fieldnames or 'student_id' not in [f.strip().lower() for f in reader.fieldnames]:
            return Response({'detail': 'CSV must have a student_id column.'}, status=status.HTTP_400_BAD_REQUEST)

        # Pre-build the set of student_ids allowed for this exam.
        exam_classroom_ids = exam.classrooms.values_list('id', flat=True)
        allowed_set = set(
            StudentProfile.objects.filter(
                classroom__in=exam_classroom_ids, is_active=True,
            ).values_list('student_id', flat=True)
        )

        errors, created, updated = [], [], []

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                student_id = row.get('student_id', '')
                score_raw = row.get('score', '')
                is_absent = row.get('is_absent', 'false').lower() in ('true', '1', 'yes')

                if not student_id:
                    errors.append({'row': i, 'error': 'student_id missing'})
                    continue

                if student_id not in allowed_set:
                    errors.append({'row': i, 'student_id': student_id,
                                   'error': 'Student not enrolled in this exam\'s classrooms.'})
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
                    if score_val < 0:
                        errors.append({'row': i, 'student_id': student_id,
                                       'error': f'Score {score_val} cannot be negative'})
                        continue
                    if score_val > float(exam.max_score):
                        errors.append({'row': i, 'student_id': student_id,
                                       'error': f'Score {score_val} exceeds max {exam.max_score}'})
                        continue
                else:
                    score_val = 0

                # update_or_create can still raise IntegrityError. The whole
                # loop runs inside one outer transaction.atomic() above, and
                # on Postgres a DB error inside an atomic block poisons the
                # rest of that transaction until it's rolled back — so this
                # needs its own nested atomic() (a savepoint) to roll back
                # just this row instead of aborting every row already
                # processed in this request.
                try:
                    with transaction.atomic():
                        obj, was_created = ExamScore.objects.update_or_create(
                            exam=exam, student=student,
                            defaults={
                                'score': score_val, 'is_absent': is_absent,
                                'remarks': row.get('remarks', ''), 'entered_by': request.user,
                            }
                        )
                    (created if was_created else updated).append(student_id)
                except IntegrityError as e:
                    errors.append({'row': i, 'student_id': student_id, 'error': f'Could not save score: {e}'})

        return Response({
            'created': len(created), 'updated': len(updated),
            'errors_count': len(errors), 'errors': errors,
        }, status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def scores_template(self, request, pk=None):
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
        absent_count = ExamScore.objects.filter(exam=exam, is_absent=True).count()

        if not scores.exists():
            # Return a full-shape response with null numeric fields so the
            # frontend can render "—" placeholders instead of "undefined%".
            # Previously returned {'detail': '...'} which was truthy, causing
            # stats.average etc. to be undefined and render as "undefined%".
            return Response({
                'exam_id': exam.id, 'exam_title': exam.title,
                'total_students': 0,
                'absent_count': absent_count,
                'average': None,
                'highest': None,
                'lowest': None,
                'pass_rate': None,
                'distribution': {'0-49': 0, '50-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0},
            })

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
            'exam_id': exam.id, 'exam_title': exam.title,
            'total_students': len(score_values),
            'absent_count': absent_count,
            'average': round(sum(percentages) / len(percentages), 1),
            'highest': round(max(percentages), 1),
            'lowest': round(min(percentages), 1),
            'pass_rate': round((len(passed) / len(score_values)) * 100, 1),
            'distribution': buckets,
        })

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        """Export the *exam list* (not scores) currently in view — respects
        whatever search/filter/ordering params are active, via
        filter_queryset(), so what downloads matches what's on screen."""
        qs = self.filter_queryset(self.get_queryset())
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Title', 'Subject', 'Classrooms', 'Type', 'Term', 'Academic Year',
            'Exam Date', 'Max Score', 'Passing Score', 'Status',
            'Students Scored', 'Average %', 'Pass Rate %', 'Created By', 'Created At',
        ])
        for exam in qs:
            present = getattr(exam, 'present_scores', None)
            if present is None:
                present = list(exam.scores.filter(is_absent=False))
            avg = None
            pass_rate = None
            if present:
                total = sum(float(s.score) for s in present)
                avg = round((total / len(present) / float(exam.max_score)) * 100, 1)
                passed = sum(1 for s in present if float(s.score) >= float(exam.passing_score))
                pass_rate = round((passed / len(present)) * 100, 1)
            writer.writerow([
                exam.title,
                exam.subject.name if exam.subject_id else '',
                ', '.join(c.name for c in exam.classrooms.all()),
                exam.get_exam_type_display(),
                exam.get_term_display(),
                exam.academic_year,
                exam.exam_date.strftime('%Y-%m-%d'),
                exam.max_score,
                exam.passing_score,
                'Published' if exam.is_published else 'Draft',
                len(present),
                avg if avg is not None else '',
                pass_rate if pass_rate is not None else '',
                exam.created_by.get_full_name() if exam.created_by_id else '',
                exam.created_at.strftime('%Y-%m-%d %H:%M') if exam.created_at else '',
            ])

        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="exams_export.csv"'
        return response

    @action(detail=False, methods=['get'], url_path='export-excel')
    def export_excel(self, request):
        """Same filtered exam list as export_csv, but as a styled workbook
        via the shared reports excel_engine (branded header, colour-coded
        pass/fail, auto-fit columns) — matching the look of every other
        export in the platform."""
        from django.http import HttpResponse
        from mathapi.apps.accounts.models import SiteSettings
        from mathapi.apps.reports.excel_engine import generate_exams_list_excel

        qs = self.filter_queryset(self.get_queryset())
        school_name = request.query_params.get('school_name') or SiteSettings.get().platform_name
        data = generate_exams_list_excel(list(qs), school_name=school_name)

        response = HttpResponse(
            data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="exams_export.xlsx"'
        return response


class ExamScoreViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['exam', 'student', 'is_absent']
    ordering_fields = ['score', 'entered_at']

    def get_permissions(self):
        # SECURITY FIX: create/update/destroy previously relied only on
        # class-level IsAuthenticated. update()/destroy() below only ever
        # restricted *teachers* to their own entries — they never blocked
        # students or parents. Since get_queryset() returns a student's own
        # scores (and a parent's linked children's scores), any student
        # could POST a brand-new score for themselves, or PATCH/DELETE an
        # existing one, effectively grading their own exam. Now gated to
        # teacher/admin, with TeacherFeatureEnabled letting an admin toggle
        # this off for teachers from Settings (folded under the "exams"
        # resource, since scores are exam data).
        from mathapi.apps.accounts.permissions import IsTeacherOrAdmin, TeacherFeatureEnabled
        if self.action == 'create':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'edit')]
        if self.action in ['update', 'partial_update']:
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'edit')]
        if self.action == 'destroy':
            return [IsTeacherOrAdmin(), TeacherFeatureEnabled('exams', 'delete')]
        return [permissions.IsAuthenticated()]

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
        if user.role == 'teacher':
            owned_exams = scope_exams(user)
            return qs.filter(exam__in=owned_exams)
        return qs.all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ExamScoreCreateSerializer
        return ExamScoreSerializer

    def perform_create(self, serializer):
        user = self.request.user
        exam = serializer.validated_data.get('exam')
        student = serializer.validated_data.get('student')
        # Teachers may only create scores for exams they own AND for
        # students enrolled in that exam's classrooms.
        if user.role == 'teacher':
            if exam and not scope_exams(user).filter(pk=exam.pk).exists():
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('You do not have access to this exam.')
            if exam and student:
                allowed = set(
                    StudentProfile.objects.filter(
                        classroom__in=exam.classrooms.all(), is_active=True,
                    ).values_list('id', flat=True)
                )
                if student.id not in allowed:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied('Student is not enrolled in this exam\'s classrooms.')
        serializer.save(entered_by=user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Teachers can only update scores they entered themselves.
        if request.user.role == 'teacher' and instance.entered_by_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only edit scores you entered.')
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user.role == 'teacher' and instance.entered_by_id != request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only delete scores you entered.')
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        score = self.get_object()
        logs = ScoreEditLog.objects.filter(exam_score=score)
        return Response(ScoreEditLogSerializer(logs, many=True).data)
