# Generated for admin-configurable teacher feature toggles.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_sitesettings_pwa_icon_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='teacher_permissions',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'Admin-configurable overrides for what teachers may do, per '
                    'resource (students/exams/classrooms/subjects) and action '
                    '(add/edit/delete). Missing keys fall back to '
                    'DEFAULT_TEACHER_PERMISSIONS. Super admins are never affected '
                    'by this — they always have full access.'
                ),
            ),
        ),
    ]
