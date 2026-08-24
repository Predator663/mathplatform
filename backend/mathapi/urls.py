from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('mathapi.apps.accounts.urls')),
    path('api/students/', include('mathapi.apps.students.urls')),
    path('api/exams/', include('mathapi.apps.exams.urls')),
    path('api/analytics/', include('mathapi.apps.analytics.urls')),
    path('api/reports/', include('mathapi.apps.reports.urls')),
    path('api/groups/', include('mathapi.apps.groups.urls')),
    path('api/notifications/', include('mathapi.apps.notifications.urls')),
    path('api/gamification/', include('mathapi.apps.gamification.urls')),
    path('api/quizzes/', include('mathapi.apps.quizzes.urls')),
    path('api/tournaments/', include('mathapi.apps.tournaments.urls')),
    path('api/leagues/', include('mathapi.apps.leagues.urls')),
    path('api/interventions/', include('mathapi.apps.interventions.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
