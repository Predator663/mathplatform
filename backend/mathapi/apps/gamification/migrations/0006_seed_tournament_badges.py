from django.db import migrations


def seed_tournament_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import TOURNAMENT_BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    for entry in TOURNAMENT_BADGE_CATALOG:
        Badge.objects.update_or_create(code=entry['code'], defaults=entry)


def unseed_tournament_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import TOURNAMENT_BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    codes = [e['code'] for e in TOURNAMENT_BADGE_CATALOG]
    Badge.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0005_seed_quiz_badges'),
    ]

    operations = [
        migrations.RunPython(seed_tournament_badges, unseed_tournament_badges),
    ]
