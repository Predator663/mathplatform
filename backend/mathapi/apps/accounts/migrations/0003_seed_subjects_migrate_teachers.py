"""
Migration 0003: Seed default subjects + migrate existing Classroom.teachers M2M
rows into TeacherAssignment rows (each teacher assigned to Mathematics).
"""
from django.db import migrations

DEFAULT_SUBJECTS = [
    ('Mathematics', 'MATH', '#6366f1', 'calculator'),
    ('Geography',   'GEO',  '#0ea5e9', 'globe'),
    ('Physics',     'PHY',  '#f59e0b', 'zap'),
    ('Chemistry',   'CHEM', '#10b981', 'flask-conical'),
    ('Biology',     'BIO',  '#84cc16', 'leaf'),
    ('English',     'ENG',  '#ec4899', 'book-open'),
    ('Kiswahili',   'KIS',  '#8b5cf6', 'languages'),
    ('History',     'HIST', '#f97316', 'landmark'),
    ('Civics',      'CIV',  '#14b8a6', 'scale'),
]


def seed_subjects_and_migrate(apps, schema_editor):
    Subject = apps.get_model('accounts', 'Subject')
    TeacherAssignment = apps.get_model('accounts', 'TeacherAssignment')
    Classroom = apps.get_model('students', 'Classroom')

    # Seed subjects
    created_subjects = {}
    for name, code, color, icon in DEFAULT_SUBJECTS:
        subj, _ = Subject.objects.get_or_create(
            code=code,
            defaults={'name': name, 'color': color, 'icon': icon, 'is_active': True},
        )
        created_subjects[code] = subj

    math = created_subjects['MATH']

    # Migrate existing Classroom.teachers M2M → TeacherAssignment rows
    # Each existing teacher is assigned to Mathematics (safe default)
    for classroom in Classroom.objects.prefetch_related('teachers').all():
        for teacher in classroom.teachers.all():
            TeacherAssignment.objects.get_or_create(
                teacher=teacher,
                classroom=classroom,
                subject=math,
            )


def reverse_migrate(apps, schema_editor):
    Subject = apps.get_model('accounts', 'Subject')
    TeacherAssignment = apps.get_model('accounts', 'TeacherAssignment')
    TeacherAssignment.objects.all().delete()
    Subject.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_subject_teacherassignment'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_subjects_and_migrate, reverse_migrate),
    ]
