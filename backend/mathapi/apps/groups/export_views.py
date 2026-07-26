from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from mathapi.apps.accounts.permissions import IsTeacherOrAdmin
from mathapi.apps.accounts.models import SiteSettings
from mathapi.apps.exams.models import Exam
from .models import StudentGroup
from .views import _owned_classroom_or_404
from . import report_engine

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
        .select_related('subject').prefetch_related('memberships__student__user')
    )
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
