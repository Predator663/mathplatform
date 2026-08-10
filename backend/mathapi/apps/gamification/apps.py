from django.apps import AppConfig


class GamificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mathapi.apps.gamification'

    def ready(self):
        from . import signals  # noqa: F401  (registers post_save/post_delete handlers)
