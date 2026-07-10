"""
Migration 0002: Add Subject model and TeacherAssignment model.
Safe to run while the old Classroom.teachers M2M still exists.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(max_length=10, unique=True)),
                ('color', models.CharField(default='#6366f1', max_length=7)),
                ('icon', models.CharField(blank=True, max_length=50, help_text='Lucide icon name, e.g. calculator')),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'db_table': 'subjects', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='TeacherAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('teacher', models.ForeignKey(
                    limit_choices_to={'role': 'teacher'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignments',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('classroom', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='teacher_assignments',
                    to='students.classroom',
                )),
                ('subject', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignments',
                    to='accounts.subject',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'teacher_assignments'},
        ),
        migrations.AddConstraint(
            model_name='teacherassignment',
            constraint=models.UniqueConstraint(
                fields=['teacher', 'classroom', 'subject'],
                name='unique_teacher_classroom_subject',
            ),
        ),
    ]
