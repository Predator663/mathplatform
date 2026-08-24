from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'seasons', views.LeagueSeasonViewSet, basename='league_season')
router.register(r'groups', views.LeagueGroupViewSet, basename='league_group')
router.register(r'promotions', views.PromotionEventViewSet, basename='league_promotion')

urlpatterns = [
    path('', include(router.urls)),
    path('hall-of-fame/', views.HallOfFameView.as_view(), name='league_hall_of_fame'),
    path('student-summary/<int:student_id>/', views.StudentLeagueSummaryView.as_view(), name='league_student_summary'),
]
