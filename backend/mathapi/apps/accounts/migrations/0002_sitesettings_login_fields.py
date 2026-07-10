from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='login_tagline',
            field=models.CharField(
                blank=True,
                default='Student Performance Analytics',
                help_text='Tagline shown under the platform name on the login page',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='login_welcome',
            field=models.CharField(
                blank=True,
                default='Sign in to your account',
                help_text='Heading shown above the login form',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='login_bg_gradient',
            field=models.BooleanField(
                default=True,
                help_text='Show ambient glow gradient on login page background',
            ),
        ),
    ]
