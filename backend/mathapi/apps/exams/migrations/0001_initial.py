from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MathTopic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('color', models.CharField(default='#6366f1', max_length=7)),
                ('level', models.CharField(
                    choices=[
                        ('primary', 'Primary (Std 1–7)'),
                        ('o_level', 'O-Level (Form 1–4)'),
                        ('a_level', 'A-Level (Form 5–6)'),
                        ('all', 'All Levels'),
                    ],
                    default='o_level',
                    max_length=20,
                )),
                ('order', models.PositiveIntegerField(default=0)),
            ],
            options={'db_table': 'math_topics', 'ordering': ['level', 'order', 'name']},
        ),
        migrations.CreateModel(
            name='Exam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('exam_type', models.CharField(
                    choices=[
                        ('monthly_test', 'Monthly Test'),
                        ('mid_term', 'Mid-Term Exam'),
                        ('terminal', 'Terminal Exam (End of Term)'),
                        ('mock', 'Mock Exam (Mazoezi)'),
                        ('necta', 'NECTA (National)'),
                        ('psle', 'PSLE (Std 7)'),
                        ('csee', 'CSEE (Form 4)'),
                        ('acsee', 'ACSEE (Form 6)'),
                        ('diagnostic', 'Diagnostic Test'),
                    ],
                    max_length=20,
                )),
                ('term', models.CharField(
                    choices=[
                        ('term_1', 'Term I (Jan–Apr)'),
                        ('term_2', 'Term II (May–Aug)'),
                        ('term_3', 'Term III (Sep–Dec)'),
                        ('annual', 'Annual'),
                    ],
                    max_length=20,
                )),
                ('academic_year', models.CharField(max_length=9)),
                ('exam_date', models.DateField()),
                ('max_score', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[django.core.validators.MinValueValidator(1)],
                )),
                ('passing_score', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('description', models.TextField(blank=True)),
                ('is_published', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_exams',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('classrooms', models.ManyToManyField(
                    blank=True,
                    related_name='exams',
                    to='students.classroom',
                )),
            ],
            options={'db_table': 'exams', 'ordering': ['-exam_date']},
        ),
        migrations.CreateModel(
            name='ExamTopicWeight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('max_marks', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('weight_percentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('exam', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='topic_weights',
                    to='exams.exam',
                )),
                ('topic', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='exam_weights',
                    to='exams.mathtopic',
                )),
            ],
            options={
                'db_table': 'exam_topic_weights',
                'unique_together': {('exam', 'topic')},
            },
        ),
        migrations.AddField(
            model_name='exam',
            name='topics',
            field=models.ManyToManyField(blank=True, through='exams.ExamTopicWeight', to='exams.mathtopic'),
        ),
        migrations.CreateModel(
            name='ExamScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('is_absent', models.BooleanField(default=False)),
                ('remarks', models.CharField(blank=True, max_length=500)),
                ('entered_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entered_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='entered_scores',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('exam', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scores',
                    to='exams.exam',
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='exam_scores',
                    to='students.studentprofile',
                )),
            ],
            options={
                'db_table': 'exam_scores',
                'ordering': ['-exam__exam_date'],
                'unique_together': {('exam', 'student')},
            },
        ),
        migrations.CreateModel(
            name='TopicScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('max_marks', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[django.core.validators.MinValueValidator(0)],
                )),
                ('exam_score', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='topic_scores',
                    to='exams.examscore',
                )),
                ('topic', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_scores',
                    to='exams.mathtopic',
                )),
            ],
            options={
                'db_table': 'topic_scores',
                'unique_together': {('exam_score', 'topic')},
            },
        ),
        migrations.CreateModel(
            name='ScoreEditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_score', models.DecimalField(decimal_places=2, max_digits=6)),
                ('new_score', models.DecimalField(decimal_places=2, max_digits=6)),
                ('reason', models.CharField(blank=True, max_length=500)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ('exam_score', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='edit_logs',
                    to='exams.examscore',
                )),
            ],
            options={'db_table': 'score_edit_logs', 'ordering': ['-changed_at']},
        ),
    ]
