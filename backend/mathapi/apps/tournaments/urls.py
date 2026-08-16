from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'tournaments', views.TournamentViewSet, basename='tournament')

urlpatterns = [
    path('', include(router.urls)),
    path('my-entries/', views.MyTournamentEntriesView.as_view(), name='tournament_my_entries'),
    path('intel/', views.TournamentIntelView.as_view(), name='tournament_intel'),
]
