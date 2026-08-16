from django.urls import path

from . import views

urlpatterns = [
    path('preferences/', views.NotificationPreferenceView.as_view(), name='notification_preferences'),
    path('history/', views.NotificationLogListView.as_view(), name='notification_history'),
    path('unread-count/', views.NotificationUnreadCountView.as_view(), name='notification_unread_count'),
    path('mark-read/', views.NotificationMarkReadView.as_view(), name='notification_mark_read'),
    path('test-email/', views.TestEmailView.as_view(), name='notification_test_email'),
    path('send-analytics-report/', views.SendAnalyticsReportView.as_view(), name='notification_send_analytics_report'),
    path('send-whatsapp-result/', views.SendWhatsAppResultView.as_view(), name='notification_send_whatsapp_result'),
    path('ping/', views.PingView.as_view(), name='notification_ping'),
    path('system-status/', views.SystemStatusView.as_view(), name='notification_system_status'),
    path('failures/', views.NotificationFailuresView.as_view(), name='notification_failures'),
    # HTTP triggers for a free external scheduler — see _CronTriggerView docstring.
    path('cron/run-alerts/', views.RunAnalyticsAlertsView.as_view(), name='notification_cron_alerts'),
    path('cron/run-digest/', views.RunDailyDigestView.as_view(), name='notification_cron_digest'),
]
