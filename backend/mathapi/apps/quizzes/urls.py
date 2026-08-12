from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'quizzes', views.DailyQuizViewSet, basename='daily-quiz')
router.register(r'scores', views.DailyQuizScoreViewSet, basename='daily-quiz-score')

urlpatterns = [
    path('', include(router.urls)),
    path('classroom/<int:classroom_id>/analytics/', views.ClassroomQuizAnalyticsView.as_view(), name='quiz_classroom_analytics'),
    path('my-progress/', views.MyQuizProgressView.as_view(), name='quiz_my_progress'),
    path('students/<int:student_id>/progress/', views.StudentQuizProgressView.as_view(), name='quiz_student_progress'),
    path('students/<int:student_id>/progress-report.pdf/', views.StudentQuizProgressPDFView.as_view(), name='quiz_student_progress_pdf'),
]
