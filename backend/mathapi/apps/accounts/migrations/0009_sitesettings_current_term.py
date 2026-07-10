# Generated manually to match 0009_sitesettings_current_term

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_sitesettings_teacher_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='current_academic_year',
            field=models.CharField(
                blank=True, default='', max_length=9,
                help_text='The school\'s current academic year (e.g. "2026"). Used to pre-fill the Academic Year field when creating a new exam.',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='current_term',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[
                    ('term_1', 'Term I (Jan–Apr)'),
                    ('term_2', 'Term II (May–Aug)'),
                    ('term_3', 'Term III (Sep–Dec)'),
                    ('annual', 'Annual'),
                ],
                help_text='The school\'s current term. Used to pre-fill the Term field when creating a new exam. Leave blank to not pre-fill.',
            ),
        ),
    ]
