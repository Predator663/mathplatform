from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
    ('exams', '0004_alter_mathtopic_name'),
]

    operations = [
        migrations.AlterUniqueTogether(
            name='mathtopic',
            unique_together={('subject', 'name')},
        ),
    ]