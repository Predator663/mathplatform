from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register('subjects', views.SubjectViewSet, basename='subject')
router.register('assignments', views.TeacherAssignmentViewSet, basename='assignment')
router.register('users', views.UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('me/', views.MeView.as_view(), name='me'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('settings/', views.SiteSettingsView.as_view(), name='site_settings'),
    path('audit-log/', views.AuditLogListView.as_view(), name='audit_log'),
    path('audit-log/facets/', views.AuditLogFacetsView.as_view(), name='audit_log_facets'),
    path('audit-log/stats/', views.AuditLogStatsView.as_view(), name='audit_log_stats'),
    path('audit-log/<int:pk>/card/pdf/', views.AuditLogCardPDFView.as_view(), name='audit_log_card_pdf'),
    path('audit-log/export/cards/pdf/', views.AuditLogExportCardsPDFView.as_view(), name='audit_log_export_cards_pdf'),
    path('audit-log/export/csv/', views.AuditLogExportCSVView.as_view(), name='audit_log_export_csv'),
]
