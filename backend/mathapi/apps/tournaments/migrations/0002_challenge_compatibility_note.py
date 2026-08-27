from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='challenge',
            name='compatibility_note',
            field=models.TextField(
                blank=True,
                default='',
                help_text=(
                    "Set when this challenge's combatants weren't a close skill-level match "
                    "at creation/edit time — an AI-written explanation of the mismatch (falls "
                    "back to a plain algorithmic sentence if Claude is unavailable), shown to "
                    "the teacher as a heads-up. Cleared automatically if a later edit brings "
                    "the combatants back within the compatibility gap. See "
                    "services.sync_compatibility_note()."
                ),
            ),
        ),
    ]
