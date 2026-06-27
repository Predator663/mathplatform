"""
Migration 0003: Data migration — assign all existing MathTopics and Exams
to the Mathematics subject.
"""
from django.db import migrations


def assign_math_subject(apps, schema_editor):
    Subject = apps.get_model('accounts', 'Subject')
    MathTopic = apps.get_model('exams', 'MathTopic')
    Exam = apps.get_model('exams', 'Exam')

    try:
        math = Subject.objects.get(code='MATH')
    except Subject.DoesNotExist:
        # Shouldn't happen after migration 0003 in accounts, but be safe
        math = Subject.objects.create(
            name='Mathematics', code='MATH', color='#6366f1', icon='calculator', is_active=True
        )

    MathTopic.objects.filter(subject__isnull=True).update(subject=math)
    Exam.objects.filter(subject__isnull=True).update(subject=math)

    # Now add unique_together on (subject, name) for MathTopic
    # This is done as a data migration so we can fix any name collisions first
    # (unlikely in a fresh install, but safe)


def reverse_assign(apps, schema_editor):
    MathTopic = apps.get_model('exams', 'MathTopic')
    Exam = apps.get_model('exams', 'Exam')
    MathTopic.objects.all().update(subject=None)
    Exam.objects.all().update(subject=None)


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0002_topic_subject_exam_subject_soft_delete'),
    ]

    operations = [
        migrations.RunPython(assign_math_subject, reverse_assign),
    ]
