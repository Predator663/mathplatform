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
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
