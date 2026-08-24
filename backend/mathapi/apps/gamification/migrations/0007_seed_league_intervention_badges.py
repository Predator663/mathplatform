from django.db import migrations


def seed_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import LEAGUE_BADGE_CATALOG, INTERVENTION_BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    for entry in LEAGUE_BADGE_CATALOG + INTERVENTION_BADGE_CATALOG:
        Badge.objects.update_or_create(code=entry['code'], defaults=entry)


def unseed_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import LEAGUE_BADGE_CATALOG, INTERVENTION_BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    codes = [e['code'] for e in LEAGUE_BADGE_CATALOG + INTERVENTION_BADGE_CATALOG]
    Badge.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0006_seed_tournament_badges'),
    ]

    operations = [
        migrations.RunPython(seed_badges, unseed_badges),
    ]
