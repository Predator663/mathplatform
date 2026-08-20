import csv
import io

from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from mathapi.apps.accounts.permissions import IsTeacherOrAdmin
from mathapi.apps.accounts.models import SiteSettings
from mathapi.apps.exams.models import Exam
from .models import StudentGroup, GroupAssignmentMemberMark, GroupAssignmentScore
from .views import _owned_classroom_or_404
from . import report_engine, services

SORT_CHOICES = {
    'name': lambda g: g.name.lower(),
    'score': lambda g: -(_group_avg(g) if _group_avg(g) is not None else -1),
    'members': lambda g: -g.memberships.count(),
}


def _group_avg(group):
    avgs = [m.average_at_placement for m in group.memberships.all() if m.average_at_placement is not None]
    return round(sum(avgs) / len(avgs), 1) if avgs else None


def _resolve_school_name(request) -> str:
    override = request.query_params.get('school_name')
    if override:
        return override
    return SiteSettings.get().platform_name


def _gather(request, classroom_id):
    """Shared setup for every group export: classroom access check, sorted
    group list, and the header meta-line block (class name + details)."""
    classroom = _owned_classroom_or_404(request.user, classroom_id)
    academic_year = request.query_params.get('academic_year') or classroom.academic_year
    sort_by = request.query_params.get('sort_by', 'name')
    if sort_by not in SORT_CHOICES:
        sort_by = 'name'

    groups = list(
        StudentGroup.objects.filter(classroom_id=classroom_id, academic_year=academic_year)
        .select_related('subject', 'stream').prefetch_related('memberships__student__user')
    )
    stream_id = request.query_params.get('stream_id')
    if stream_id:
        groups = [g for g in groups if g.stream_id is None or str(g.stream_id) == str(stream_id)]
    # Same "subject" filter the groups list / auto-generate use — without
    # this, choosing a subject in the UI filtered what you saw on screen
    # but the exported file still contained every group in the classroom.
    subject_id = request.query_params.get('subject_id')
    if subject_id:
        groups = [g for g in groups if g.subject_id is None or str(g.subject_id) == str(subject_id)]
    term_id = request.query_params.get('term')
    if term_id:
        groups = [g for g in groups if not g.term or g.term == term_id]
    groups.sort(key=SORT_CHOICES[sort_by])

    subject_name = None
    if groups and groups[0].subject_id and len({g.subject_id for g in groups}) == 1:
        subject_name = groups[0].subject.name

    term_display = None
    term_val = request.query_params.get('term')
    if term_val:
        term_display = dict(Exam.Term.choices).get(term_val, term_val)

    extra = {
        'school_name': _resolve_school_name(request),
        'academic_year': academic_year,
        'subject_name': subject_name,
        'term_display': term_display,
        'generated_by': request.user.get_full_name() or request.user.email,
    }
    extra['meta_lines'] = report_engine._meta_lines(classroom, extra)
    return classroom, groups, extra


class GroupsSummaryPDFView(APIView):
    """GET /api/groups/export/classroom/<id>/summary/pdf/?sort_by=name|score|members"""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom, groups, extra = _gather(request, classroom_id)
        if not groups:
            return Response({'detail': 'No groups found for this classroom yet.'}, status=404)
        pdf_bytes = report_engine.generate_groups_summary_pdf(classroom, groups, extra)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="groups_summary_{safe}.pdf"'
        return response


class GroupsSummaryExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom, groups, extra = _gather(request, classroom_id)
        if not groups:
            return Response({'detail': 'No groups found for this classroom yet.'}, status=404)
        xl_bytes = report_engine.generate_groups_summary_excel(classroom, groups, extra)
        response = HttpResponse(
            xl_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="groups_summary_{safe}.xlsx"'
        return response


class GroupsRosterPDFView(APIView):
    """GET /api/groups/export/classroom/<id>/roster/pdf/?sort_by=name|score|members
    Detailed export: each group's badge/logo, name, and its member list with scores."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom, groups, extra = _gather(request, classroom_id)
        if not groups:
            return Response({'detail': 'No groups found for this classroom yet.'}, status=404)
        pdf_bytes = report_engine.generate_groups_roster_pdf(classroom, groups, extra)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="groups_roster_{safe}.pdf"'
        return response


class GroupsRosterExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom, groups, extra = _gather(request, classroom_id)
        if not groups:
            return Response({'detail': 'No groups found for this classroom yet.'}, status=404)
        xl_bytes = report_engine.generate_groups_roster_excel(classroom, groups, extra)
        response = HttpResponse(
            xl_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="groups_roster_{safe}.xlsx"'
        return response


# ── Group work (assignment) analytics exports ────────────────────────────────

def _gather_group_work_analytics(request, classroom_id):
    """Shared setup for group-work analytics exports: classroom access
    check, computed analytics (same filters the analytics page uses), and
    the standard header meta-line block."""
    classroom = _owned_classroom_or_404(request.user, classroom_id)
    params = request.query_params
    academic_year = params.get('academic_year') or classroom.academic_year
    created_by_id = request.user.id if request.user.role == 'teacher' else None

    analytics = services.get_group_assignment_analytics(
        classroom_id,
        stream_id=params.get('stream_id') or None,
        group_id=params.get('group_id') or None,
        subject_id=params.get('subject_id') or None,
        term=params.get('term') or None,
        academic_year=academic_year,
        assignment_type=params.get('assignment_type') or None,
        date_from=params.get('date_from') or None,
        date_to=params.get('date_to') or None,
        created_by_id=created_by_id,
    )

    subject_name = None
    subject_id = params.get('subject_id')
    if subject_id:
        from mathapi.apps.accounts.models import Subject
        subject = Subject.objects.filter(id=subject_id).first()
        subject_name = subject.name if subject else None

    term_display = None
    term_val = params.get('term')
    if term_val:
        term_display = dict(Exam.Term.choices).get(term_val, term_val)

    extra = {
        'school_name': _resolve_school_name(request),
        'academic_year': academic_year,
        'subject_name': subject_name,
        'term_display': term_display,
        'generated_by': request.user.get_full_name() or request.user.email,
    }
    extra['meta_lines'] = report_engine._meta_lines(classroom, extra)
    return classroom, analytics, extra


class GroupWorkAnalyticsPDFView(APIView):
    """GET /api/groups/export/classroom/<id>/assignments/analytics/pdf/
    Same filters as the analytics endpoint (stream_id, group_id, subject_id,
    term, academic_year, assignment_type, date_from, date_to)."""
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom, analytics, extra = _gather_group_work_analytics(request, classroom_id)
        if not analytics['per_group']:
            return Response({'detail': 'No group-assignment marks recorded for this selection yet.'}, status=404)
        pdf_bytes = report_engine.generate_group_work_analytics_pdf(classroom, analytics, extra)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="group_work_analytics_{safe}.pdf"'
        return response


class GroupWorkAnalyticsExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom, analytics, extra = _gather_group_work_analytics(request, classroom_id)
        if not analytics['per_group']:
            return Response({'detail': 'No group-assignment marks recorded for this selection yet.'}, status=404)
        xl_bytes = report_engine.generate_group_work_analytics_excel(classroom, analytics, extra)
        response = HttpResponse(
            xl_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="group_work_analytics_{safe}.xlsx"'
        return response


class GroupAssignmentMarksCSVView(APIView):
    """
    GET /api/groups/export/classroom/<id>/assignments/marks/csv/
    ?stream_id=&group_id=&subject_id=&term=&academic_year=&assignment_type=&date_from=&date_to=
    Raw, one-row-per-student export of every recorded group-assignment
    mark — the format best suited to further analysis in a spreadsheet
    tool, distinct from the PDF/Excel summary reports above.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin]

    def get(self, request, classroom_id):
        classroom = _owned_classroom_or_404(request.user, classroom_id)
        params = request.query_params
        filters = services._group_assignment_score_filters(
            classroom_id,
            stream_id=params.get('stream_id') or None,
            group_id=params.get('group_id') or None,
            subject_id=params.get('subject_id') or None,
            term=params.get('term') or None,
            academic_year=params.get('academic_year') or classroom.academic_year,
            assignment_type=params.get('assignment_type') or None,
            date_from=params.get('date_from') or None,
            date_to=params.get('date_to') or None,
            created_by_id=request.user.id if request.user.role == 'teacher' else None,
        )
        marks = (
            GroupAssignmentMemberMark.objects.filter(group_score__in=GroupAssignmentScore.objects.filter(filters))
            .select_related(
                'group_score__assignment', 'group_score__group', 'group_score__group__stream',
                'student__user', 'student__stream',
            )
            .order_by('group_score__assignment__date_given', 'group_score__group__name', 'student__user__first_name')
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Assignment', 'Type', 'Date Given', 'Subject', 'Term', 'Academic Year',
            'Group', 'Stream', 'Group Score', 'Max Score', 'Group %',
            'Student', 'Student ID', 'Adjustment', 'Excused', 'Effective Score', 'Effective %', 'Note',
        ])
        for mark in marks:
            gs = mark.group_score
            a = gs.assignment
            writer.writerow([
                a.title, a.get_assignment_type_display(), a.date_given.isoformat(),
                a.subject.name if a.subject_id else '', a.get_term_display() if a.term else '', a.academic_year,
                gs.group.name, gs.group.stream.name if gs.group.stream_id else '',
                gs.score, a.max_score, gs.percentage,
                mark.student.full_name, mark.student.student_id,
                mark.adjustment, 'Yes' if mark.is_excused else 'No',
                mark.effective_score, mark.percentage, mark.note,
            ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="group_assignment_marks_{safe}.csv"'
        return response
