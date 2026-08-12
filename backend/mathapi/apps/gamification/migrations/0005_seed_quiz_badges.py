from django.db import migrations


def seed_quiz_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import QUIZ_BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    for entry in QUIZ_BADGE_CATALOG:
        Badge.objects.update_or_create(code=entry['code'], defaults=entry)


def unseed_quiz_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import QUIZ_BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    codes = [e['code'] for e in QUIZ_BADGE_CATALOG]
    Badge.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0004_studentbadge_quiz_quizstreak_student'),
    ]

    operations = [
        migrations.RunPython(seed_quiz_badges, unseed_quiz_badges),
    ]
