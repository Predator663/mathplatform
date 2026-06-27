from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GradeLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('short_name', models.CharField(blank=True, max_length=20)),
                ('education_level', models.CharField(
                    choices=[
                        ('pre_primary', 'Pre-Primary (Awali)'),
                        ('primary', 'Primary (Msingi)'),
                        ('o_level', 'O-Level (Form 1–4)'),
                        ('a_level', 'A-Level (Form 5–6)'),
                        ('technical', 'Technical / VETA'),
                    ],
                    default='o_level',
                    max_length=20,
                )),
                ('order', models.PositiveIntegerField(default=0)),
                ('necta_exam', models.CharField(blank=True, max_length=50)),
                ('math_subject', models.CharField(blank=True, default='Mathematics', max_length=100)),
            ],
            options={'db_table': 'grade_levels', 'ordering': ['order']},
        ),
        migrations.CreateModel(
            name='Classroom',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('stream', models.CharField(
                    blank=True,
                    choices=[
                        ('general', 'General'),
                        ('science', 'Science'),
                        ('arts', 'Arts'),
                        ('commerce', 'Commerce'),
                        ('technical', 'Technical'),
                    ],
                    default='general',
                    max_length=20,
                )),
                ('academic_year', models.CharField(max_length=9)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('grade_level', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='classrooms',
                    to='students.gradelevel',
                )),
                ('teachers', models.ManyToManyField(
                    blank=True,
                    limit_choices_to={'role': 'teacher'},
                    related_name='classrooms',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'classrooms',
                'ordering': ['grade_level__order', 'name'],
                'unique_together': {('name', 'grade_level', 'academic_year')},
            },
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_id', models.CharField(max_length=20, unique=True)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('enrollment_date', models.DateField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('index_number', models.CharField(blank=True, max_length=30)),
                ('parent_name', models.CharField(blank=True, max_length=200)),
                ('parent_phone', models.CharField(blank=True, max_length=20)),
                ('district', models.CharField(blank=True, max_length=100)),
                ('region', models.CharField(blank=True, max_length=100)),
                ('classroom', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='student_profiles',
                    to='students.classroom',
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'student_profiles',
                'ordering': ['user__last_name', 'user__first_name'],
            },
        ),
        migrations.CreateModel(
            name='ParentStudentLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('relationship', models.CharField(default='Parent', max_length=50)),
                ('is_primary', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(
                    limit_choices_to={'role': 'parent'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='linked_students',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='parent_links',
                    to='students.studentprofile',
                )),
            ],
            options={
                'db_table': 'parent_student_links',
                'unique_together': {('parent', 'student')},
            },
        ),
    ]
