from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.DashboardSummaryView.as_view(), name='dashboard'),
    path('students/<int:student_id>/summary/', views.StudentSummaryView.as_view(), name='student_summary'),
    path('students/<int:student_id>/trend/', views.StudentTrendView.as_view(), name='student_trend'),
    path('students/<int:student_id>/topics/', views.StudentTopicAnalysisView.as_view(), name='student_topics'),
    path('classrooms/<int:classroom_id>/', views.ClassAnalyticsView.as_view(), name='class_analytics'),
    path('classrooms/<int:classroom_id>/heatmap/', views.TopicHeatmapView.as_view(), name='topic_heatmap'),
    path('at-risk/', views.AtRiskStudentsView.as_view(), name='at_risk'),
    path('compare/', views.ComparativeAnalysisView.as_view(), name='compare'),
]
