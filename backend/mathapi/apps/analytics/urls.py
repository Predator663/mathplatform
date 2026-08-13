from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.DashboardSummaryView.as_view(), name='dashboard'),
    path('students/<int:student_id>/summary/', views.StudentSummaryView.as_view(), name='student_summary'),
    path('students/<int:student_id>/trend/', views.StudentTrendView.as_view(), name='student_trend'),
    path('students/<int:student_id>/topics/', views.StudentTopicAnalysisView.as_view(), name='student_topics'),
    path('students/<int:student_id>/classroom-comparison/', views.StudentClassroomComparisonView.as_view(), name='student_classroom_comparison'),
    path('students/compare/', views.StudentComparisonView.as_view(), name='student_comparison'),
    path('students/compare/pdf/', views.StudentComparisonPDFView.as_view(), name='student_comparison_pdf'),
    path('classrooms/<int:classroom_id>/', views.ClassAnalyticsView.as_view(), name='class_analytics'),
    path('classrooms/<int:classroom_id>/heatmap/', views.TopicHeatmapView.as_view(), name='topic_heatmap'),
    path('at-risk/', views.AtRiskStudentsView.as_view(), name='at_risk'),
    path('compare/', views.ComparativeAnalysisView.as_view(), name='compare'),
    path('classrooms/<int:classroom_id>/stream-comparison/', views.StreamComparisonView.as_view(), name='stream_comparison'),

    # ── Intelligence layer ────────────────────────────────────────────
    path('integrity/', views.IntegrityFlagsView.as_view(), name='integrity_flags'),
    path('students/<int:student_id>/risk/', views.StudentRiskScoreView.as_view(), name='student_risk'),
    path('classrooms/<int:classroom_id>/risk/', views.ClassroomRiskScoresView.as_view(), name='classroom_risk'),
    path('classrooms/<int:classroom_id>/topic-dependencies/', views.TopicDependencyChainsView.as_view(), name='topic_dependencies'),
    path('teacher-consistency/', views.TeacherGradingConsistencyView.as_view(), name='teacher_consistency'),
    path('students/<int:student_id>/boundary-whatif/', views.GradeBoundaryWhatIfView.as_view(), name='boundary_whatif'),
]
