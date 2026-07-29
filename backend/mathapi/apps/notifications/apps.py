from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mathapi.apps.notifications'
    label = 'notifications'
    verbose_name = 'Notifications'
