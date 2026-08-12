from django.apps import AppConfig


class QuizzesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mathapi.apps.quizzes'
    # No signals of its own — DailyQuizScore's post_save/post_delete
    # handlers live in gamification.signals (registered when that app's
    # AppConfig.ready() runs), to keep gamification logic in one place.
