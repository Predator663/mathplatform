from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'programs', views.InterventionProgramViewSet, basename='intervention_program')
router.register(r'stages', views.InterventionStageViewSet, basename='intervention_stage')

urlpatterns = [
    path('', include(router.urls)),
    path('candidates/', views.SlowLearnerCandidatesView.as_view(), name='intervention_candidates'),
    path('analytics/', views.InterventionAnalyticsView.as_view(), name='intervention_analytics'),
    path('default-template/', views.DefaultStageTemplateView.as_view(), name='intervention_default_template'),
]
