from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_merge_login_fields_subject_scoping'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='privacy_policy',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Privacy Policy page content (plain text / markdown-ish, line breaks preserved)',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='terms_of_use',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Terms of Use page content (plain text / markdown-ish, line breaks preserved)',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='about_me',
            field=models.TextField(
                blank=True,
                default='',
                help_text='About page content (plain text / markdown-ish, line breaks preserved)',
            ),
        ),
    ]
