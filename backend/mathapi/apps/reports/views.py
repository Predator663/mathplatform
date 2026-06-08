from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from mathapi.apps.analytics import services
from mathapi.apps.students.models import StudentProfile, Classroom
from mathapi.apps.exams.models import Exam, ExamScore
from .pdf_engine import (
    generate_exam_scores_pdf,
    generate_class_report_pdf,
    generate_student_report_pdf,
)
from .excel_engine import (
    generate_exam_scores_excel,
    generate_class_report_excel,
)
import csv
import io


SORT_CHOICES = ['name', 'score_desc', 'score_asc', 'grade', 'student_id',
                'average_desc', 'average_asc']


class StudentReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        summary = services.get_student_summary(student_id)
        trend = services.get_student_trend(student_id)
        topics = services.get_student_topic_analysis(student_id)
        return Response({'summary': summary, 'trend': trend, 'topic_analysis': topics})


class ClassReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')
        data = services.get_class_analytics(classroom_id, academic_year=academic_year, term=term)
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
            exam = Exam.objects.prefetch_related('classrooms', 'topic_weights__topic').get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'detail': 'Exam not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = request.query_params.get('school_name', 'School of Excellence')

        scores = ExamScore.objects.filter(exam=exam).select_related(
            'student__user', 'student__classroom__grade_level'
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
        try:
            classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = request.query_params.get('school_name', 'School of Excellence')
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')

        students = StudentProfile.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('user').order_by('user__last_name', 'user__first_name')

        exam_filters = {'classrooms': classroom}
        if academic_year:
            exam_filters['academic_year'] = academic_year
        if term:
            exam_filters['term'] = term
        exams = Exam.objects.filter(**exam_filters).order_by('exam_date')

        # Build scores_map: {student_id: {exam_id: percentage}}
        scores_map = {s.id: {} for s in students}
        all_scores = ExamScore.objects.filter(
            student__in=students, exam__in=exams, is_absent=False
        ).select_related('student', 'exam')
        for sc in all_scores:
            scores_map[sc.student_id][sc.exam_id] = sc.percentage

        pdf_bytes = generate_class_report_pdf(
            classroom, students, scores_map, exams,
            sort_by=sort_by, school_name=school_name
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = str(classroom).replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="class_{safe}_report.pdf"'
        return response


class StudentReportPDFView(APIView):
    """GET /api/reports/export/student/:id/pdf/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        try:
            student = StudentProfile.objects.select_related(
                'user', 'classroom__grade_level'
            ).get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'detail': 'Student not found.'}, status=404)

        school_name = request.query_params.get('school_name', 'School of Excellence')

        scores = ExamScore.objects.filter(
            student=student
        ).select_related('exam').order_by('exam__exam_date')

        topic_result = services.get_student_topic_analysis(student_id)
        topic_data = topic_result.get('topics', [])

        pdf_bytes = generate_student_report_pdf(
            student, scores, topic_data, school_name=school_name
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        safe = student.full_name.replace(' ', '_')[:40]
        response['Content-Disposition'] = f'attachment; filename="student_{safe}_report.pdf"'
        return response


# ── Excel Exports ─────────────────────────────────────────────────────────────

class ExamScoresExcelView(APIView):
    """GET /api/reports/export/exam/:id/excel/?sort_by=name"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        try:
            exam = Exam.objects.prefetch_related('classrooms').get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'detail': 'Exam not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = request.query_params.get('school_name', 'School of Excellence')

        scores = ExamScore.objects.filter(exam=exam).select_related('student__user')
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
        try:
            classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
        except Classroom.DoesNotExist:
            return Response({'detail': 'Classroom not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        if sort_by not in SORT_CHOICES:
            sort_by = 'name'
        school_name = request.query_params.get('school_name', 'School of Excellence')
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')

        students = StudentProfile.objects.filter(
            classroom=classroom, is_active=True
        ).select_related('user').order_by('user__last_name')

        exam_filters = {'classrooms': classroom}
        if academic_year: exam_filters['academic_year'] = academic_year
        if term: exam_filters['term'] = term
        exams = Exam.objects.filter(**exam_filters).order_by('exam_date')

        scores_map = {s.id: {} for s in students}
        for sc in ExamScore.objects.filter(student__in=students, exam__in=exams, is_absent=False).select_related('student','exam'):
            scores_map[sc.student_id][sc.exam_id] = sc.percentage

        xlsx_bytes = generate_class_report_excel(
            classroom, students, scores_map, exams,
            sort_by=sort_by, school_name=school_name
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
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'detail': 'Exam not found.'}, status=404)

        sort_by = request.query_params.get('sort_by', 'name')
        scores = list(ExamScore.objects.filter(exam=exam).select_related('student__user'))

        sort_map = {
            'name':       lambda s: s.student.full_name.lower(),
            'score_desc': lambda s: -float(s.score),
            'score_asc':  lambda s: float(s.score),
            'student_id': lambda s: s.student.student_id,
        }
        scores.sort(key=sort_map.get(sort_by, sort_map['name']))

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'Student Name', 'Score', 'Max Score', 'Percentage', 'Grade', 'Passed', 'Absent', 'Remarks'])
        for s in scores:
            writer.writerow([
                s.student.student_id, s.student.full_name,
                float(s.score), float(exam.max_score),
                s.percentage, s.letter_grade,
                'Yes' if s.passed else 'No',
                'Yes' if s.is_absent else 'No',
                s.remarks,
            ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="scores_{exam_id}.csv"'
        return response


class ExportClassCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        students = StudentProfile.objects.filter(
            classroom_id=classroom_id, is_active=True
        ).select_related('user').order_by('user__last_name')

        sort_by = request.query_params.get('sort_by', 'name')
        students = list(students)
        if sort_by == 'student_id':
            students.sort(key=lambda s: s.student_id)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'First Name', 'Last Name', 'Email', 'Classroom', 'Enrolled'])
        for s in students:
            writer.writerow([s.student_id, s.user.first_name, s.user.last_name,
                              s.email, str(s.classroom) if s.classroom else '', str(s.enrollment_date)])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="class_{classroom_id}_students.csv"'
        return response
