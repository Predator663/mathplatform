from django.urls import path
from . import views

urlpatterns = [
    # JSON reports
    path('student/<int:student_id>/', views.StudentReportView.as_view(), name='student_report'),
    path('classroom/<int:classroom_id>/', views.ClassReportView.as_view(), name='class_report'),

    # PDF exports
    path('export/exam/<int:exam_id>/pdf/', views.ExamScoresPDFView.as_view(), name='exam_pdf'),
    path('export/classroom/<int:classroom_id>/pdf/', views.ClassReportPDFView.as_view(), name='class_pdf'),
    path('export/student/<int:student_id>/pdf/', views.StudentReportPDFView.as_view(), name='student_pdf'),

    # Excel exports
    path('export/exam/<int:exam_id>/excel/', views.ExamScoresExcelView.as_view(), name='exam_excel'),
    path('export/classroom/<int:classroom_id>/excel/', views.ClassReportExcelView.as_view(), name='class_excel'),
    path('export/student/<int:student_id>/excel/', views.StudentReportExcelView.as_view(), name='student_excel'),

    # CSV exports
    path('export/exam/<int:exam_id>/csv/', views.ExportScoresCSVView.as_view(), name='exam_csv'),
    path('export/classroom/<int:classroom_id>/csv/', views.ExportClassCSVView.as_view(), name='class_csv'),

    # All-subjects analytics report
    path('export/classroom/<int:classroom_id>/analytics/pdf/',
         views.AnalyticsReportPDFView.as_view(), name='analytics_pdf'),
    path('export/classroom/<int:classroom_id>/analytics/excel/',
         views.AnalyticsReportExcelView.as_view(), name='analytics_excel'),
]
