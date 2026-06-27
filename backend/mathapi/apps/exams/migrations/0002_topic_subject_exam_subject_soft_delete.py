"""
Migration 0002: Add MathTopic.subject FK, Exam.subject FK, Exam.is_deleted,
ExamScore non-negative CheckConstraint, and drop MathTopic.level.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0001_initial'),
        ('accounts', '0003_seed_subjects_migrate_teachers'),
    ]

    operations = [
        # Add subject FK to MathTopic (nullable during migration)
        migrations.AddField(
            model_name='mathtopic',
            name='subject',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='topics',
                to='accounts.subject',
            ),
        ),
        # Add is_active to MathTopic
        migrations.AddField(
            model_name='mathtopic',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        # Remove MathTopic.level (replaced by subject scoping)
        migrations.RemoveField(
            model_name='mathtopic',
            name='level',
        ),
        # Remove old unique_together that only covered name
        migrations.AlterUniqueTogether(
            name='mathtopic',
            unique_together=set(),
        ),
        # Add subject FK to Exam (nullable during migration)
        migrations.AddField(
            model_name='exam',
            name='subject',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='exams',
                to='accounts.subject',
            ),
        ),
        # Add soft-delete flag to Exam
        migrations.AddField(
            model_name='exam',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        # Add CheckConstraint for non-negative scores
        migrations.AddConstraint(
            model_name='examscore',
            constraint=models.CheckConstraint(
                check=models.Q(score__gte=0),
                name='examscore_score_non_negative',
            ),
        ),
        # Update MathTopic ordering now that level is gone
        migrations.AlterModelOptions(
            name='mathtopic',
            options={'db_table': 'math_topics', 'ordering': ['subject__name', 'order', 'name']},
        ),
    ]
