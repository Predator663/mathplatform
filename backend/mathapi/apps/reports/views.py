from django.http import HttpResponse
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from mathapi.apps.analytics import services
from mathapi.apps.analytics.views import _check_student_access, _get_subject_id, _get_stream_id
from mathapi.apps.accounts.scoping import assert_classroom_owned, scope_exams, get_teacher_classrooms
from mathapi.apps.accounts.models import SiteSettings
from mathapi.apps.students.models import StudentProfile, Classroom
from mathapi.apps.exams.models import Exam, ExamScore
from mathapi.apps.gamification.models import StudentBadge
from .pdf_engine import (
    generate_exam_scores_pdf,
    generate_class_report_pdf,
    generate_student_report_pdf,
    generate_at_risk_pdf,
    generate_tournament_dossier_pdf,
    generate_challenge_matchups_pdf,
    generate_hall_of_fame_pdf,
    generate_league_season_pdf,
)
from .excel_engine import (
    generate_exam_scores_excel,
    generate_class_report_excel,
    generate_student_report_excel,
    generate_tournament_dossier_excel,
    generate_hall_of_fame_excel,
)
import csv
import io


SORT_CHOICES = ['name', 'score_desc', 'score_asc', 'grade', 'student_id',
                'average_desc', 'average_asc']


def _classroom_top_achievers(students, limit=10):
    """Ranks the given students by total badges earned (all sources), for
    the class report's 'Top Achievers' section. Returns
    [{'student', 'badge_count', 'latest_badge'}, ...] sorted descending,
    students with zero badges excluded."""
    student_ids = [s.id for s in students]
    counts = (
        StudentBadge.objects.filter(student_id__in=student_ids)
        .values('student_id').annotate(count=Count('id')).order_by('-count')
    )
    count_map = {row['student_id']: row['count'] for row in counts}
    latest_map = {}
    for sb in (
        StudentBadge.objects.filter(student_id__in=student_ids)
        .select_related('badge').order_by('student_id', '-awarded_at')
    ):
        latest_map.setdefault(sb.student_id, sb.badge)

    students_by_id = {s.id: s for s in students}
    ranked = sorted(count_map.items(), key=lambda kv: -kv[1])[:limit]
    return [
        {'student': students_by_id[sid], 'badge_count': cnt, 'latest_badge': latest_map.get(sid)}
        for sid, cnt in ranked if sid in students_by_id
    ]


def _student_prizes(student_id):
    """Shared by both the PDF and Excel student-report views: every badge
    earned (exam, quiz, and tournament alike) plus a tournament record
    summary, so 'all prizes a student has won' is one call away for either
    report engine."""
    badges = list(
        StudentBadge.objects.filter(student_id=student_id)
        .select_related('badge').order_by('-awarded_at')
    )
    from mathapi.apps.tournaments.services import get_student_tournament_stats
    tournament_stats = get_student_tournament_stats(student_id)
    return badges, tournament_stats


def _student_league_intervention(student_id):
    """
    League standing + intervention programme history for one student —
    teacher/admin-only data. The caller (StudentReportPDFView/ExcelView)
    only invokes this when the requester's role is 'teacher' or
    'super_admin'; a student pulling her own report never triggers this,
    so the report generators never even receive the data to render.
    """
    from mathapi.apps.leagues.services import get_student_league_summary
    from mathapi.apps.interventions.models import InterventionProgram

    league_summary = get_student_league_summary(student_id)

    programs = InterventionProgram.objects.filter(student_id=student_id).order_by('-started_at')
    intervention_summary = [
        {
            'trigger_reason': p.trigger_reason,
            'status_label': p.get_status_display(),
            'stage_count': p.stage_count,
            'completed_stage_count': p.completed_stage_count,
            'baseline_average': p.baseline_average,
            'latest_average': p.latest_average,
            'improvement': p.improvement,
        }
        for p in programs
    ]
    return league_summary, intervention_summary


def _classroom_league_intervention(students):
    """
    Per-student league band + intervention status for the class report's
    'League Standing & Interventions' section — only students with a
    league membership or an intervention programme on record are
    included, so the section stays empty (and un-rendered) for classrooms
    that never used either feature.
    """
    from mathapi.apps.leagues.models import LeagueMembership
    from mathapi.apps.interventions.models import InterventionProgram

    student_ids = [s.id for s in students]
    students_by_id = {s.id: s for s in students}

    league_by_student = {}
    for m in (
        LeagueMembership.objects.filter(student_id__in=student_ids, season__status='active')
        .select_related('group').order_by('student_id', '-joined_at')
    ):
        league_by_student.setdefault(m.student_id, m)

    intervention_by_student = {}
    for p in (
        InterventionProgram.objects.filter(student_id__in=student_ids, status=InterventionProgram.Status.ACTIVE)
        .order_by('student_id', '-started_at')
    ):
        intervention_by_student.setdefault(p.student_id, p)

    rows = []
    for sid in set(league_by_student) | set(intervention_by_student):
        student = students_by_id.get(sid)
        if not student:
            continue
        membership = league_by_student.get(sid)
        program = intervention_by_student.get(sid)
        rows.append({
            'student': student,
            'league_band': membership.group.name if membership else None,
            'league_color': membership.group.color if membership else None,
            'is_promotion_pending': membership.is_promotion_pending if membership else False,
            'intervention_status': program.get_status_display() if program else None,
            'intervention_progress': f'{program.completed_stage_count}/{program.stage_count}' if program else None,
            'intervention_improvement': program.improvement if program else None,
        })
    rows.sort(key=lambda r: r['student'].full_name.lower())
    return rows


def _resolve_site_name(request) -> str:
    """
    Resolve the name that should appear on every generated report header.

    Always reflects whatever is configured on the Settings page
    (SiteSettings.platform_name), so report headers stay in sync with the
    rest of the app. An explicit ?school_name= override is still honoured
    for callers that need a one-off custom label.
    """
    override = request.query_params.get('school_name')
    if override:
        return override
    return SiteSettings.get().platform_name


class StudentReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        _check_student_access(request.user, student_id)
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        summary = services.get_student_summary(student_id, created_by_id=created_by_id)
        trend = services.get_student_trend(student_id, created_by_id=created_by_id)
        topics = services.get_student_topic_analysis(student_id, created_by_id=created_by_id)
        return Response({'summary': summary, 'trend': trend, 'topic_analysis': topics})


class ClassReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom_id)
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        data = services.get_class_analytics(
            classroom_id, academic_year=academic_year, term=term, created_by_id=created_by_id,
        )
        return Response(data)


# ── PDF Exports ───────────────────────────────────────────────────────────────

class ExamScoresPDFView(APIView):
    """
    GET /api/reports/export/exam/:id/pdf/
    ?sort_by=name|score_desc|score_asc|grade|student_id
    ?school_name=My+School
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        try:
            exam = scope_exams(
                request.user,
                Exam.objects.prefetch_related('classrooms', 'topic_weights__topic'),
            ).get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'detail': 'Exam not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = _resolve_site_name(request)

        scores = ExamScore.objects.filter(exam=exam).select_related(
            'student__user', 'student__classroom__grade_level', 'student__stream'
        ).prefetch_related('topic_scores__topic')

        pdf_bytes = generate_exam_scores_pdf(exam, scores, sort_by=sort_by, school_name=school_name)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe_title = exam.title.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="exam_{safe_title}_scores.pdf"'
        return response


class ClassReportPDFView(APIView):
    """
    GET /api/reports/export/classroom/:id/pdf/
    ?sort_by=name|average_desc|average_asc|student_id
    ?academic_year=2024/2025 &term=term_1
    ?school_name=My+School
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom_id)
        try:
            classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = _resolve_site_name(request)
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')

        students = StudentProfile.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('user', 'stream').order_by('user__last_name', 'user__first_name')

        exam_filters = {'classrooms': classroom}
        if academic_year:
            exam_filters['academic_year'] = academic_year
        if term:
            exam_filters['term'] = term
        exams = scope_exams(request.user, Exam.objects.filter(**exam_filters)).order_by('exam_date')

        # Build scores_map: {student_id: {exam_id: percentage}}
        scores_map = {s.id: {} for s in students}
        all_scores = ExamScore.objects.filter(
            student__in=students, exam__in=exams, is_absent=False
        ).select_related('student', 'exam')
        for sc in all_scores:
            scores_map[sc.student_id][sc.exam_id] = sc.percentage

        top_achievers = _classroom_top_achievers(list(students))
        league_intervention = _classroom_league_intervention(list(students))

        pdf_bytes = generate_class_report_pdf(
            classroom, students, scores_map, exams,
            sort_by=sort_by, school_name=school_name, top_achievers=top_achievers,
            league_intervention=league_intervention,
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="class_{safe}_report.pdf"'
        return response


class StudentReportPDFView(APIView):
    """GET /api/reports/export/student/:id/pdf/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        _check_student_access(request.user, student_id)
        try:
            student = StudentProfile.objects.select_related(
                'user', 'classroom__grade_level'
            ).get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=404)

        school_name = _resolve_site_name(request)

        scores = ExamScore.objects.filter(
            student=student
        ).select_related('exam').order_by('exam__exam_date')
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        if created_by_id:
            scores = scores.filter(exam__created_by_id=created_by_id)

        topic_result = services.get_student_topic_analysis(student_id, created_by_id=created_by_id)
        topic_data = topic_result.get('topics', [])
        trend = services.get_student_trend(student_id, created_by_id=created_by_id)
        comparison = services.get_student_classroom_comparison(student_id, created_by_id=created_by_id)
        badges, tournament_stats = _student_prizes(student_id)
        league_summary = intervention_summary = None
        if request.user.role in ('teacher', 'super_admin'):
            league_summary, intervention_summary = _student_league_intervention(student_id)

        pdf_bytes = generate_student_report_pdf(
            student, scores, topic_data, school_name=school_name, trend=trend, comparison=comparison,
            badges=badges, tournament_stats=tournament_stats,
            league_summary=league_summary, intervention_summary=intervention_summary,
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = student.full_name.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="student_{safe}_report.pdf"'
        return response


class StudentReportExcelView(APIView):
    """GET /api/reports/export/student/:id/excel/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        _check_student_access(request.user, student_id)
        try:
            student = StudentProfile.objects.select_related(
                'user', 'classroom__grade_level'
            ).get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=404)

        school_name = _resolve_site_name(request)

        scores = ExamScore.objects.filter(
            student=student
        ).select_related('exam').order_by('exam__exam_date')
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        if created_by_id:
            scores = scores.filter(exam__created_by_id=created_by_id)

        topic_result = services.get_student_topic_analysis(student_id, created_by_id=created_by_id)
        topic_data = topic_result.get('topics', [])
        trend = services.get_student_trend(student_id, created_by_id=created_by_id)
        comparison = services.get_student_classroom_comparison(student_id, created_by_id=created_by_id)
        badges, tournament_stats = _student_prizes(student_id)
        league_summary = intervention_summary = None
        if request.user.role in ('teacher', 'super_admin'):
            league_summary, intervention_summary = _student_league_intervention(student_id)

        xlsx_bytes = generate_student_report_excel(
            student, scores, topic_data, school_name=school_name, trend=trend, comparison=comparison,
            badges=badges, tournament_stats=tournament_stats,
            league_summary=league_summary, intervention_summary=intervention_summary,
        )

        response = HttpResponse(
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        safe = student.full_name.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="student_{safe}_report.xlsx"'
        return response


# ── Excel Exports ─────────────────────────────────────────────────────────────

class ExamScoresExcelView(APIView):
    """GET /api/reports/export/exam/:id/excel/?sort_by=name"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        try:
            exam = scope_exams(request.user, Exam.objects.prefetch_related('classrooms')).get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'detail': 'Exam not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = _resolve_site_name(request)

        scores = ExamScore.objects.filter(exam=exam).select_related('student__user', 'student__stream')
        xlsx_bytes = generate_exam_scores_excel(exam, scores, sort_by=sort_by, school_name=school_name)

        response = HttpResponse(xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        safe = exam.title.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="exam_{safe}_scores.xlsx"'
        return response


class ClassReportExcelView(APIView):
    """GET /api/reports/export/classroom/:id/excel/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom_id)
        try:
            classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = _resolve_site_name(request)
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')

        students = StudentProfile.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('user', 'stream').order_by('user__last_name')

        exam_filters = {'classrooms': classroom}
        if academic_year: exam_filters['academic_year'] = academic_year
        if term: exam_filters['term'] = term
        exams = scope_exams(request.user, Exam.objects.filter(**exam_filters)).order_by('exam_date')

        scores_map = {s.id: {} for s in students}
        for sc in ExamScore.objects.filter(student__in=students, exam__in=exams, is_absent=False).select_related('student','exam'):
            scores_map[sc.student_id][sc.exam_id] = sc.percentage

        top_achievers = _classroom_top_achievers(list(students))
        league_intervention = _classroom_league_intervention(list(students))

        xlsx_bytes = generate_class_report_excel(
            classroom, students, scores_map, exams,
            sort_by=sort_by, school_name=school_name, top_achievers=top_achievers,
            league_intervention=league_intervention,
        )

        response = HttpResponse(xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="class_{safe}_report.xlsx"'
        return response


# ── CSV Exports (legacy) ──────────────────────────────────────────────────────

class ExportScoresCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        try:
            exam = scope_exams(request.user, Exam.objects.all()).get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'detail': 'Exam not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        scores = list(ExamScore.objects.filter(exam=exam).select_related('student__user', 'student__stream'))

        sort_map = {
            'name':       lambda s: s.student.full_name.lower(),
            'score_desc': lambda s: -float(s.score),
            'score_asc':  lambda s: float(s.score),
            'student_id': lambda s: s.student.student_id,
        }
        scores.sort(key=sort_map.get(sort_by, sort_map['name']))

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f'{_resolve_site_name(request)} — {exam.title} Scores'])
        writer.writerow(['Student ID', 'Student Name', 'Stream', 'Score', 'Max Score', 'Percentage', 'Grade', 'Passed', 'Absent', 'Remarks'])
        for s in scores:
            stream_name = s.student.stream.name if s.student.stream_id else ''
            if s.is_absent:
                writer.writerow([
                    s.student.student_id, s.student.full_name, stream_name,
                    'ABSENT', float(exam.max_score), '—', '—',
                    '—', 'Yes', s.remarks,
                ])
            else:
                writer.writerow([
                    s.student.student_id, s.student.full_name, stream_name,
                    float(s.score), float(exam.max_score),
                    s.percentage, s.letter_grade,
                    'Yes' if s.passed else 'No',
                    'No', s.remarks,
                ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="scores_{exam_id}.csv"'
        return response


class ExportClassCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom_id)
        students = StudentProfile.objects.filter(
            classroom_id=classroom_id, is_active=True
        ).select_related('user', 'stream').order_by('user__last_name')

        sort_by = request.query_params.get('sort_by', 'name')
        students = list(students)
        if sort_by == 'student_id':
            students.sort(key=lambda s: s.student_id)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f'{_resolve_site_name(request)} — Class Student List'])
        writer.writerow(['Student ID', 'First Name', 'Last Name', 'Email', 'Classroom', 'Stream', 'Enrolled'])
        for s in students:
            writer.writerow([s.student_id, s.user.first_name, s.user.last_name,
                              s.email, str(s.classroom) if s.classroom else '',
                              s.stream.name if s.stream_id else '', str(s.enrollment_date)])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="class_{classroom_id}_students.csv"'
        return response


# ── All-Subjects Analytics Report ─────────────────────────────────────────────

class AnalyticsReportPDFView(APIView):
    """
    GET /api/reports/export/classroom/<id>/analytics/pdf/
    ?academic_year=2024&term=term_1&subject_id=3
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom_id)
        try:
            Classroom.objects.get(id=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=404)

        from .analytics_report_engine import build_analytics_report_data, generate_analytics_report_pdf

        academic_year = request.query_params.get('academic_year')
        term          = request.query_params.get('term')
        subject_id    = request.query_params.get('subject_id')
        exam_id       = request.query_params.get('exam_id')
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        school_name   = _resolve_site_name(request)

        try:
            data = build_analytics_report_data(
                classroom_id,
                academic_year=academic_year,
                term=term,
                subject_id=int(subject_id) if subject_id else None,
                created_by_id=created_by_id,
                exam_id=int(exam_id) if exam_id else None,
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return Response({'detail': str(exc)}, status=500)

        pdf_bytes = generate_analytics_report_pdf(data, school_name=school_name)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        cls_name = data['classroom']['name'].replace(' ', '_')[:30]
        response['Content-Disposition'] = (
            f'attachment; filename="analytics_{cls_name}_{data["classroom"]["academic_year"]}.pdf"'
        )
        return response


class AnalyticsReportExcelView(APIView):
    """
    GET /api/reports/export/classroom/<id>/analytics/excel/
    ?academic_year=2024&term=term_1&subject_id=3
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        if request.user.role == 'teacher':
            assert_classroom_owned(request.user, classroom_id)
        try:
            Classroom.objects.get(id=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=404)

        from .analytics_report_engine import build_analytics_report_data, generate_analytics_report_excel

        academic_year = request.query_params.get('academic_year')
        term          = request.query_params.get('term')
        subject_id    = request.query_params.get('subject_id')
        exam_id       = request.query_params.get('exam_id')
        created_by_id = request.user.id if request.user.role == 'teacher' else None
        school_name   = _resolve_site_name(request)

        try:
            data = build_analytics_report_data(
                classroom_id,
                academic_year=academic_year,
                term=term,
                subject_id=int(subject_id) if subject_id else None,
                created_by_id=created_by_id,
                exam_id=int(exam_id) if exam_id else None,
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return Response({'detail': str(exc)}, status=500)

        xl_bytes = generate_analytics_report_excel(data, school_name=school_name)
        response = HttpResponse(
            xl_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        cls_name = data['classroom']['name'].replace(' ', '_')[:30]
        response['Content-Disposition'] = (
            f'attachment; filename="analytics_{cls_name}_{data["classroom"]["academic_year"]}.xlsx"'
        )
        return response


class AtRiskPDFView(APIView):
    """
    GET /api/reports/export/at-risk/pdf/
    ?classroom_id=&threshold=&subject_id=&stream_id=
    ?sort_by=score_asc|score_desc|name|classroom
    ?trend=declining|stable|improving
    ?school_name=My+School
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        classroom_id = request.query_params.get('classroom_id')
        threshold = float(request.query_params.get('threshold', 30))
        subject_id = _get_subject_id(request)
        stream_id = _get_stream_id(request)
        sort_by = request.query_params.get('sort_by', 'score_asc')
        if sort_by not in ('score_asc', 'score_desc', 'name', 'classroom'):
            sort_by = 'score_asc'
        trend = request.query_params.get('trend')
        if trend not in ('declining', 'stable', 'improving'):
            trend = None
        school_name = _resolve_site_name(request)

        if classroom_id and user.role == 'teacher':
            assert_classroom_owned(user, int(classroom_id))

        if user.role == 'teacher' and not classroom_id:
            classroom_ids = list(get_teacher_classrooms(user).values_list('id', flat=True))
        else:
            classroom_ids = [int(classroom_id)] if classroom_id else None

        created_by_id = user.id if user.role == 'teacher' else None
        students = services.get_at_risk_students(
            classroom_ids=classroom_ids,
            threshold=threshold,
            subject_id=subject_id,
            created_by_id=created_by_id,
            stream_id=stream_id,
            trend=trend,
        )

        scope_label = 'All Classrooms' if not classroom_id else None
        if classroom_id:
            try:
                scope_label = str(Classroom.objects.get(id=classroom_id))
            except Classroom.DoesNotExist:
                scope_label = 'Selected Classroom'

        meta = {'threshold': threshold, 'scope_label': scope_label, 'trend': trend}
        pdf_bytes = generate_at_risk_pdf(students, meta, sort_by=sort_by, school_name=school_name)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="at_risk_students.pdf"'
        return response


class TournamentDossierPDFView(APIView):
    """
    GET /api/reports/export/tournament/<tournament_id>/pdf/?school_name=
    FBI/CIA-style intel dossier: leaderboard, score distribution, headline
    callouts, and the full challenge log. Scoped the same way the
    tournaments app itself scopes access (teachers only see tournaments
    they created; admins see everything).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, tournament_id):
        from mathapi.apps.accounts.scoping import scope_tournaments
        from mathapi.apps.tournaments import services as tournament_services
        from mathapi.apps.tournaments.models import Tournament
        from django.shortcuts import get_object_or_404

        tournament = get_object_or_404(
            scope_tournaments(request.user).select_related('exam', 'classroom'),
            id=tournament_id,
        )
        school_name = _resolve_site_name(request)
        dossier = tournament_services.get_tournament_dossier(tournament)
        analytics = tournament_services.get_tournament_analytics(tournament)

        pdf_bytes = generate_tournament_dossier_pdf(tournament, dossier, analytics, school_name=school_name)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = tournament.title.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="tournament_{safe}_dossier.pdf"'
        return response


class ChallengeMatchupsPDFView(APIView):
    """
    GET /api/reports/export/tournament/<tournament_id>/matchups/pdf/?school_name=
    "Who am I facing?" sheet — just the declared duels and who's still
    unmatched, no scores/analytics. Open to anyone who can already view
    the tournament (students included — same scoping as the tournament
    detail endpoint), since this is the one students actually want.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, tournament_id):
        from mathapi.apps.accounts.scoping import scope_tournaments
        from mathapi.apps.tournaments import services as tournament_services
        from django.shortcuts import get_object_or_404

        tournament = get_object_or_404(
            scope_tournaments(request.user).select_related('exam', 'classroom'),
            id=tournament_id,
        )
        school_name = _resolve_site_name(request)
        challenges = tournament.challenges.prefetch_related(
            'entries__student__user', 'entries__stream', 'winner__student__user', 'winner__stream',
        ).all()
        unmatched_entries = list(
            tournament.entries.filter(withdrawn=False, challenges__isnull=True)
            .select_related('student__user', 'stream').distinct()
        )
        unregistered_students = list(tournament_services.get_unregistered_students(tournament))

        pdf_bytes = generate_challenge_matchups_pdf(
            tournament, challenges, unmatched_entries, school_name=school_name,
            unregistered_students=unregistered_students,
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = tournament.title.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="tournament_{safe}_matchups.pdf"'
        return response


class TournamentDossierExcelView(APIView):
    """GET /api/reports/export/tournament/<tournament_id>/excel/?school_name="""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, tournament_id):
        from mathapi.apps.accounts.scoping import scope_tournaments
        from mathapi.apps.tournaments import services as tournament_services
        from django.shortcuts import get_object_or_404

        tournament = get_object_or_404(
            scope_tournaments(request.user).select_related('exam', 'classroom'),
            id=tournament_id,
        )
        school_name = _resolve_site_name(request)
        dossier = tournament_services.get_tournament_dossier(tournament)
        analytics = tournament_services.get_tournament_analytics(tournament)

        xlsx_bytes = generate_tournament_dossier_excel(tournament, dossier, analytics, school_name=school_name)
        response = HttpResponse(xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        safe = tournament.title.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="tournament_{safe}_dossier.xlsx"'
        return response


class HallOfFamePDFView(APIView):
    """
    GET /api/reports/export/hall-of-fame/pdf/?classroom=<id>&school_name=
    Scoped the same way the leagues app scopes access (teacher/admin
    only); omit `classroom` for the school-wide Hall of Fame.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from mathapi.apps.accounts.scoping import assert_classroom_owned, get_teacher_classrooms
        from mathapi.apps.leagues import services as league_services
        from django.shortcuts import get_object_or_404
        from rest_framework.exceptions import PermissionDenied

        if request.user.role not in ('teacher', 'super_admin'):
            raise PermissionDenied('League Hall of Fame is a teacher/admin view.')

        classroom = None
        classrooms = None
        scope_label = 'All Classrooms'
        classroom_id = request.query_params.get('classroom')
        if classroom_id:
            classroom = get_object_or_404(Classroom, id=classroom_id)
            if request.user.role == 'teacher':
                assert_classroom_owned(request.user, classroom.id)
            scope_label = str(classroom)
        elif request.user.role == 'teacher':
            classrooms = get_teacher_classrooms(request.user)

        school_name = _resolve_site_name(request)
        hof = league_services.get_hall_of_fame(
            classroom=classroom, classrooms=classrooms, limit=int(request.query_params.get('limit', 15)),
        )

        pdf_bytes = generate_hall_of_fame_pdf(hof, scope_label=scope_label, school_name=school_name)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="hall_of_fame.pdf"'
        return response


class HallOfFameExcelView(APIView):
    """GET /api/reports/export/hall-of-fame/excel/?classroom=<id>&school_name="""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from mathapi.apps.accounts.scoping import assert_classroom_owned, get_teacher_classrooms
        from mathapi.apps.leagues import services as league_services
        from django.shortcuts import get_object_or_404
        from rest_framework.exceptions import PermissionDenied

        if request.user.role not in ('teacher', 'super_admin'):
            raise PermissionDenied('League Hall of Fame is a teacher/admin view.')

        classroom = None
        classrooms = None
        scope_label = 'All Classrooms'
        classroom_id = request.query_params.get('classroom')
        if classroom_id:
            classroom = get_object_or_404(Classroom, id=classroom_id)
            if request.user.role == 'teacher':
                assert_classroom_owned(request.user, classroom.id)
            scope_label = str(classroom)
        elif request.user.role == 'teacher':
            classrooms = get_teacher_classrooms(request.user)

        school_name = _resolve_site_name(request)
        hof = league_services.get_hall_of_fame(
            classroom=classroom, classrooms=classrooms, limit=int(request.query_params.get('limit', 15)),
        )

        xlsx_bytes = generate_hall_of_fame_excel(hof, scope_label=scope_label, school_name=school_name)
        response = HttpResponse(xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="hall_of_fame.xlsx"'
        return response


class LeagueSeasonRosterPDFView(APIView):
    """
    GET /api/reports/export/league-season/<id>/roster/pdf/?school_name=
    Exports the band-by-band student listing shown on the League Season
    page (the BandCard grid) — one section per band, each member's
    trend/standing exactly as the cards show it. Scoped the same way the
    leagues app scopes every other season endpoint: a teacher only ever
    sees seasons on classrooms she owns.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, season_id):
        from django.shortcuts import get_object_or_404
        from rest_framework.exceptions import PermissionDenied
        from mathapi.apps.accounts.scoping import scope_league_seasons
        from mathapi.apps.leagues import services as league_services

        if request.user.role not in ('teacher', 'super_admin'):
            raise PermissionDenied('Skill Leagues is a teacher/admin view.')

        season = get_object_or_404(
            scope_league_seasons(request.user).select_related('classroom', 'baseline_exam'),
            id=season_id,
        )
        analytics = league_services.get_league_analytics(season)
        school_name = _resolve_site_name(request)
        extra = {'school_name': school_name, 'academic_year': season.classroom.academic_year}

        pdf_bytes = generate_league_season_pdf(season, analytics, extra)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = season.title.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="league_{safe}_roster.pdf"'
        return response
