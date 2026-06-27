from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('topics', views.MathTopicViewSet, basename='mathtopic')
router.register('exams', views.ExamViewSet, basename='exam')
router.register('scores', views.ExamScoreViewSet, basename='examscore')

urlpatterns = [
    path('', include(router.urls)),
]
