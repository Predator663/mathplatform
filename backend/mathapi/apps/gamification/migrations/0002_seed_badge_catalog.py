from django.db import migrations


def seed_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    for entry in BADGE_CATALOG:
        Badge.objects.update_or_create(code=entry['code'], defaults=entry)


def unseed_badges(apps, schema_editor):
    from mathapi.apps.gamification.catalog import BADGE_CATALOG
    Badge = apps.get_model('gamification', 'Badge')
    codes = [e['code'] for e in BADGE_CATALOG]
    Badge.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gamification', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_badges, unseed_badges),
    ]
