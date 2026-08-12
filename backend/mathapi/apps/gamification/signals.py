from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from mathapi.apps.exams.models import ExamScore
from mathapi.apps.quizzes.models import DailyQuizScore
from . import services


@receiver(post_save, sender=ExamScore)
def on_score_saved(sender, instance, **kwargs):
    # Gamification is a nice-to-have layered on top of scoring — a bug here
    # must never block a teacher from saving a mark.
    try:
        services.process_score_saved(instance)
    except Exception:
        pass


@receiver(post_delete, sender=ExamScore)
def on_score_deleted(sender, instance, **kwargs):
    try:
        if instance.exam.is_published:
            services.recalculate_streak(instance.student)
    except Exception:
        pass


@receiver(post_save, sender=DailyQuizScore)
def on_quiz_score_saved(sender, instance, **kwargs):
    try:
        services.process_quiz_score_saved(instance)
    except Exception:
        pass


@receiver(post_delete, sender=DailyQuizScore)
def on_quiz_score_deleted(sender, instance, **kwargs):
    try:
        if not instance.quiz.is_deleted:
            services.recalculate_quiz_streak(instance.student)
    except Exception:
        pass
