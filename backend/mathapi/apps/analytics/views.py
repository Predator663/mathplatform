from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from collections import defaultdict
from . import services


def _get_subject_id(request):
    """Extract optional subject_id from query params."""
    sid = request.query_params.get('subject_id')
    if sid:
        try:
            return int(sid)
        except (ValueError, TypeError):
            pass
    return None


def _check_student_access(user, student_id):
    """Raise PermissionDenied if user (teacher/student/parent) can't access this student."""
    if user.role == 'super_admin':
        return
    if user.role == 'teacher':
        from mathapi.apps.accounts.scoping import get_teacher_classrooms
        from mathapi.apps.students.models import StudentProfile
        from rest_framework.exceptions import PermissionDenied, NotFound
        try:
            sp = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            raise NotFound('Student not found.')
        if not get_teacher_classrooms(user).filter(id=sp.classroom_id).exists():
            raise PermissionDenied('You do not have access to this student.')
        return
    if user.role == 'student':
        from rest_framework.exceptions import PermissionDenied
        try:
            if user.student_profile.id != int(student_id):
                raise PermissionDenied('You can only view your own analytics.')
        except Exception:
            raise PermissionDenied('Forbidden.')
        return
    if user.role == 'parent':
        from rest_framework.exceptions import PermissionDenied
        if not user.linked_students.filter(student_id=student_id).exists():
            raise PermissionDenied('You do not have access to this student.')
        return
    from rest_framework.exceptions import PermissionDenied
    raise PermissionDenied('Forbidden.')


class StudentSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        _check_student_access(request.user, student_id)
        subject_id = _get_subject_id(request)
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        data = services.get_student_summary(student_id, subject_id=subject_id, created_by_id=created_by_id)
        return Response(data)


class StudentTrendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        _check_student_access(request.user, student_id)
        exam_type = request.query_params.get('exam_type')
        term = request.query_params.get('term')
        subject_id = _get_subject_id(request)
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        data = services.get_student_trend(
            student_id, exam_type=exam_type, term=term,
            subject_id=subject_id, created_by_id=created_by_id,
        )
        return Response(data)


class StudentTopicAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        _check_student_access(request.user, student_id)
        subject_id = _get_subject_id(request)
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        data = services.get_student_topic_analysis(
            student_id, subject_id=subject_id, created_by_id=created_by_id,
        )
        return Response(data)


class ClassAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        user = request.user
        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import assert_classroom_owned
            assert_classroom_owned(user, classroom_id)
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')
        subject_id = _get_subject_id(request)
        created_by_id = user.id if user.role == 'teacher' else None
        data = services.get_class_analytics(
            classroom_id, academic_year=academic_year, term=term,
            subject_id=subject_id, created_by_id=created_by_id,
        )
        return Response(data)


class TopicHeatmapView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        user = request.user
        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import assert_classroom_owned
            assert_classroom_owned(user, classroom_id)
        academic_year = request.query_params.get('academic_year')
        subject_id = _get_subject_id(request)
        created_by_id = user.id if user.role == 'teacher' else None
        data = services.get_topic_class_heatmap(
            classroom_id, academic_year=academic_year,
            subject_id=subject_id, created_by_id=created_by_id,
        )
        return Response(data)


class AtRiskStudentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        classroom_id = request.query_params.get('classroom_id')
        threshold = float(request.query_params.get('threshold', 50))
        subject_id = _get_subject_id(request)

        if classroom_id and user.role == 'teacher':
            from mathapi.apps.accounts.scoping import assert_classroom_owned
            assert_classroom_owned(user, int(classroom_id))

        if user.role == 'teacher' and not classroom_id:
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            classroom_ids = list(get_teacher_classrooms(user).values_list('id', flat=True))
        else:
            classroom_ids = [int(classroom_id)] if classroom_id else None

        created_by_id = user.id if user.role == 'teacher' else None
        data = services.get_at_risk_students(
            classroom_ids=classroom_ids,
            threshold=threshold,
            subject_id=subject_id,
            created_by_id=created_by_id,
        )
        return Response({'at_risk': data, 'count': len(data)})


class ComparativeAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        ids_param = request.query_params.get('classroom_ids', '')
        try:
            classroom_ids = [int(i) for i in ids_param.split(',') if i.strip()]
        except ValueError:
            return Response({'detail': 'Invalid classroom_ids.'}, status=status.HTTP_400_BAD_REQUEST)
        if not classroom_ids:
            return Response({'detail': 'Provide at least one classroom_id.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            allowed = set(get_teacher_classrooms(user).values_list('id', flat=True))
            forbidden = [cid for cid in classroom_ids if cid not in allowed]
            if forbidden:
                return Response({'detail': f'Access denied for classrooms: {forbidden}'}, status=status.HTTP_403_FORBIDDEN)

        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')
        subject_id = _get_subject_id(request)
        created_by_id = user.id if user.role == 'teacher' else None
        data = services.get_comparative_analysis(
            classroom_ids, academic_year=academic_year, term=term,
            subject_id=subject_id, created_by_id=created_by_id,
        )
        return Response(data)


class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Count, Q as DQ
        from mathapi.apps.students.models import StudentProfile, Classroom
        from mathapi.apps.exams.models import Exam, ExamScore

        user = request.user
        subject_id = _get_subject_id(request)

        # ── percentage helper ─────────────────────────────────────────
        # NOTE: this used to be computed as a raw DB expression
        # (F('score') * 100.0 / F('exam__max_score')) via ExpressionWrapper.
        # That mixes a DecimalField with a Python float literal — Django
        # requires an explicit output_field on the INNER combined
        # expression too, not just the outer wrapper, or it raises
        # FieldError: "Expression contains mixed types...". SQLite is
        # lenient about this and let it slide, but Postgres (production)
        # raised it on every request, so the dashboard API call 500'd —
        # and since the frontend query never checked isError, it silently
        # rendered as 0s and empty graphs instead of a visible failure.
        # Every OTHER analytics endpoint in this app (services.py)
        # computes percentage in Python via ExamScore.percentage /
        # TopicScore.percentage, so we do the same here for correctness
        # and consistency.
        def pct(score, max_score):
            if not max_score:
                return None
            return round((float(score) / float(max_score)) * 100, 1)

        def letter_grade(pct):
            if pct is None:
                return None
            if pct >= 75: return 'A'
            if pct >= 65: return 'B'
            if pct >= 45: return 'C'
            if pct >= 30: return 'D'
            return 'F'

        if user.role == 'student':
            try:
                return Response(services.get_student_summary(user.student_profile.id))
            except Exception:
                return Response({})

        # ── Scope classrooms ────────────────────────────────────────────
        if user.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            classroom_qs = get_teacher_classrooms(user)
        else:
            classroom_qs = Classroom.objects.filter(is_active=True)

        classroom_ids = list(classroom_qs.values_list('id', flat=True))

        # ── Scope exams ─────────────────────────────────────────────────
        exam_filter = DQ(classrooms__in=classroom_ids, is_deleted=False)
        if subject_id:
            exam_filter &= DQ(subject_id=subject_id)
        if user.role == 'teacher':
            exam_filter &= DQ(created_by=user)
        exam_qs = Exam.objects.filter(exam_filter).distinct()

        # ── Scope scores ────────────────────────────────────────────────
        score_filter = DQ(student__classroom_id__in=classroom_ids, is_absent=False)
        if subject_id:
            score_filter &= DQ(exam__subject_id=subject_id)
        if user.role == 'teacher':
            score_filter &= DQ(exam__created_by=user)

        # ── Counts (cheap) ──────────────────────────────────────────────
        total_students = StudentProfile.objects.filter(
            classroom_id__in=classroom_ids, is_active=True
        ).count()
        total_exams = exam_qs.count()
        total_classrooms = len(classroom_ids)

        # ── Recent exams list ───────────────────────────────────────────
        recent_exams_qs = (
            exam_qs.filter(is_published=True)
            .select_related('subject')
            .order_by('-exam_date')[:5]
        )
        recent_exam_ids = [e.id for e in recent_exams_qs]

        # ── Overall average + grade distribution ────────────────────────
        # Fetch (score, max_score) pairs and compute in Python.
        scored_rows = list(
            ExamScore.objects.filter(score_filter)
            .filter(exam__max_score__gt=0)
            .values_list('score', 'exam__max_score')
        )
        all_pcts = [pct(s, m) for s, m in scored_rows]
        overall_avg = None
        grade_distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        valid = [p for p in all_pcts if p is not None]
        if valid:
            overall_avg = round(sum(valid) / len(valid), 1)
            for p in valid:
                g = letter_grade(p)
                if g in grade_distribution:
                    grade_distribution[g] += 1

        # ── At-risk count ───────────────────────────────────────────────
        # Reuses services.get_at_risk_students() — the same canonical
        # definition (recent-3-exam average < threshold, OR a >10pt drop
        # across those 3 exams) used by AtRiskPage / AtRiskStudentsView.
        # This used to be reimplemented here with only the "below 30%"
        # half of the rule and no declining check, so the dashboard tile
        # could show a different count than the dedicated At-Risk page for
        # the exact same students. Single source of truth now.
        created_by_id = user.id if user.role == 'teacher' else None
        at_risk_count = len(services.get_at_risk_students(
            classroom_ids=classroom_ids,
            threshold=30.0,
            subject_id=subject_id,
            created_by_id=created_by_id,
        ))

        # ── Per-classroom averages ───────────────────────────────────────
        classroom_rows = (
            ExamScore.objects.filter(score_filter)
            .filter(exam__max_score__gt=0)
            .values_list('student__classroom_id', 'student__classroom__name', 'score', 'exam__max_score')
        )
        classroom_pcts: dict = defaultdict(list)
        classroom_names: dict = {}
        for cid, cname, score, max_score in classroom_rows:
            p = pct(score, max_score)
            if p is not None:
                classroom_pcts[cid].append(p)
                classroom_names[cid] = cname
        student_counts = dict(
            StudentProfile.objects.filter(classroom_id__in=classroom_ids, is_active=True)
            .values('classroom_id')
            .annotate(cnt=Count('id'))
            .values_list('classroom_id', 'cnt')
        )
        classroom_averages = sorted([
            {
                'classroom': classroom_names[cid],
                'average': round(sum(pcts) / len(pcts), 1),
                'student_count': student_counts.get(cid, 0),
            }
            for cid, pcts in classroom_pcts.items()
        ], key=lambda c: c['classroom'])[:12]

        # ── Recent exam stats ────────────────────────────────────────────
        exam_pcts: dict = defaultdict(list)
        for exam_id, score, max_score in (
            ExamScore.objects.filter(exam_id__in=recent_exam_ids, is_absent=False)
            .filter(exam__max_score__gt=0)
            .values_list('exam_id', 'score', 'exam__max_score')
        ):
            p = pct(score, max_score)
            if p is not None:
                exam_pcts[exam_id].append(p)

        recent_exam_stats = []
        for e in recent_exams_qs:
            pcts = exam_pcts.get(e.id, [])
            if pcts:
                avg_val = round(sum(pcts) / len(pcts), 1)
                pass_rate = round(100 * sum(1 for p in pcts if p >= 30) / len(pcts), 1)
            else:
                avg_val, pass_rate = None, None
            recent_exam_stats.append({
                'id': e.id, 'title': e.title, 'exam_date': str(e.exam_date),
                'average': avg_val, 'pass_rate': pass_rate,
            })

        # ── Per-subject averages (admin only) ────────────────────────────
        subject_averages = []
        if user.role == 'super_admin':
            subj_rows = (
                ExamScore.objects.filter(
                    is_absent=False, student__classroom_id__in=classroom_ids,
                )
                .filter(exam__max_score__gt=0)
                .values_list(
                    'exam__subject_id', 'exam__subject__name', 'exam__subject__code',
                    'exam__subject__color', 'score', 'exam__max_score',
                    'exam_id', 'student_id',
                )
            )
            subj_pcts: dict = defaultdict(list)
            subj_meta: dict = {}
            subj_exam_ids: dict = defaultdict(set)
            subj_student_ids: dict = defaultdict(set)
            for sid_key, sname, scode, scolor, score, max_score, exam_id, student_id in subj_rows:
                p = pct(score, max_score)
                if p is not None:
                    subj_pcts[sid_key].append(p)
                    subj_meta[sid_key] = (sname, scode, scolor)
                    subj_exam_ids[sid_key].add(exam_id)
                    subj_student_ids[sid_key].add(student_id)

            for sid_key, pcts in subj_pcts.items():
                sname, scode, scolor = subj_meta[sid_key]
                passed = sum(1 for p in pcts if p >= 30)
                subject_averages.append({
                    'subject': sname,
                    'code': scode,
                    'color': scolor,
                    'average': round(sum(pcts) / len(pcts), 1),
                    'pass_rate': round(100 * passed / len(pcts), 1),
                    'student_count': len(subj_student_ids[sid_key]),
                    'exam_count': len(subj_exam_ids[sid_key]),
                })
            subject_averages.sort(key=lambda s: -s['average'])

        # ── Per-teacher stats (admin only) ───────────────────────────────
        teacher_stats = []
        if user.role == 'super_admin':
            t_filter = DQ(is_absent=False, student__classroom_id__in=classroom_ids)
            if subject_id:
                t_filter &= DQ(exam__subject_id=subject_id)
            teacher_rows = (
                ExamScore.objects.filter(t_filter)
                .filter(exam__max_score__gt=0)
                .values_list(
                    'exam__created_by_id', 'exam__created_by__first_name',
                    'exam__created_by__last_name', 'exam__created_by__email',
                    'score', 'exam__max_score', 'exam_id', 'student_id',
                )
            )
            teacher_pcts: dict = defaultdict(list)
            teacher_meta: dict = {}
            teacher_exam_ids: dict = defaultdict(set)
            teacher_student_ids: dict = defaultdict(set)
            for tid, fn, ln, email, score, max_score, exam_id, student_id in teacher_rows:
                p = pct(score, max_score)
                if p is not None:
                    teacher_pcts[tid].append(p)
                    teacher_meta[tid] = (fn or '', ln or '', email)
                    teacher_exam_ids[tid].add(exam_id)
                    teacher_student_ids[tid].add(student_id)

            for tid, pcts in teacher_pcts.items():
                fn, ln, email = teacher_meta[tid]
                full_name = f'{fn} {ln}'.strip() or email
                passed = sum(1 for p in pcts if p >= 30)
                teacher_stats.append({
                    'teacher': full_name,
                    'email': email,
                    'average': round(sum(pcts) / len(pcts), 1),
                    'pass_rate': round(100 * passed / len(pcts), 1),
                    'exam_count': len(teacher_exam_ids[tid]),
                    'student_count': len(teacher_student_ids[tid]),
                })
            teacher_stats.sort(key=lambda t: -t['average'])

        return Response({
            'total_students': total_students,
            'total_classrooms': total_classrooms,
            'total_exams': total_exams,
            'at_risk_count': at_risk_count,
            'overall_average': overall_avg,
            'grade_distribution': grade_distribution,
            'classroom_averages': classroom_averages,
            'subject_averages': subject_averages,
            'teacher_stats': teacher_stats,
            'recent_exams': [
                {'id': e.id, 'title': e.title, 'exam_type': e.exam_type,
                 'exam_date': str(e.exam_date), 'term': e.term,
                 'subject': e.subject.name if e.subject_id else None}
                for e in recent_exams_qs
            ],
            'recent_exam_stats': recent_exam_stats,
        })
