from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from . import services


class StudentSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        user = request.user
        # Students can only see their own data
        if user.role == 'student':
            try:
                if user.student_profile.id != int(student_id):
                    return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
            except Exception:
                return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        data = services.get_student_summary(student_id)
        return Response(data)


class StudentTrendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        exam_type = request.query_params.get('exam_type')
        term = request.query_params.get('term')
        data = services.get_student_trend(student_id, exam_type=exam_type, term=term)
        return Response(data)


class StudentTopicAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, student_id):
        data = services.get_student_topic_analysis(student_id)
        return Response(data)


class ClassAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')
        data = services.get_class_analytics(classroom_id, academic_year=academic_year, term=term)
        return Response(data)


class TopicHeatmapView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        academic_year = request.query_params.get('academic_year')
        data = services.get_topic_class_heatmap(classroom_id, academic_year=academic_year)
        return Response(data)


class AtRiskStudentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        classroom_id = request.query_params.get('classroom_id')
        threshold = float(request.query_params.get('threshold', 50))
        data = services.get_at_risk_students(
            classroom_id=int(classroom_id) if classroom_id else None,
            threshold=threshold,
        )
        return Response({'at_risk': data, 'count': len(data)})


class ComparativeAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ids_param = request.query_params.get('classroom_ids', '')
        try:
            classroom_ids = [int(i) for i in ids_param.split(',') if i.strip()]
        except ValueError:
            return Response({'detail': 'Invalid classroom_ids.'}, status=status.HTTP_400_BAD_REQUEST)
        if not classroom_ids:
            return Response({'detail': 'Provide at least one classroom_id.'}, status=status.HTTP_400_BAD_REQUEST)
        academic_year = request.query_params.get('academic_year')
        term = request.query_params.get('term')
        data = services.get_comparative_analysis(classroom_ids, academic_year=academic_year, term=term)
        return Response(data)


class DashboardSummaryView(APIView):
    """Aggregated stats for the admin/teacher dashboard."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from mathapi.apps.students.models import StudentProfile, Classroom
        from mathapi.apps.exams.models import Exam, ExamScore

        user = request.user

        if user.role == 'student':
            try:
                student = user.student_profile
                return Response(services.get_student_summary(student.id))
            except Exception:
                return Response({})

        # Teacher / Admin dashboard
        if user.role == 'teacher':
            classroom_qs = Classroom.objects.filter(teachers=user)
        else:
            classroom_qs = Classroom.objects.filter(is_active=True)

        total_students = StudentProfile.objects.filter(
            classroom__in=classroom_qs, is_active=True
        ).count()

        total_exams = Exam.objects.filter(classrooms__in=classroom_qs).distinct().count()

        recent_exams = Exam.objects.filter(
            classrooms__in=classroom_qs, is_published=True
        ).order_by('-exam_date')[:5]

        at_risk = services.get_at_risk_students()
        at_risk_count = len(at_risk)

        all_scores = ExamScore.objects.filter(
            student__classroom__in=classroom_qs, is_absent=False
        )
        overall_avg = None
        if all_scores.exists():
            pcts = [s.percentage for s in all_scores]
            overall_avg = round(sum(pcts) / len(pcts), 1)

        return Response({
            'total_students': total_students,
            'total_classrooms': classroom_qs.count(),
            'total_exams': total_exams,
            'at_risk_count': at_risk_count,
            'overall_average': overall_avg,
            'recent_exams': [
                {
                    'id': e.id,
                    'title': e.title,
                    'exam_type': e.exam_type,
                    'exam_date': str(e.exam_date),
                    'term': e.term,
                }
                for e in recent_exams
            ],
        })
