from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('students', '0002_alter_studentprofile_index_number'),
        ('accounts', '0009_sitesettings_current_term'),
        ('exams', '0005_add_mathtopic_subject_name_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('academic_year', models.CharField(max_length=9)),
                ('term', models.CharField(
                    blank=True,
                    choices=[
                        ('term_1', 'Term I (Jan–Apr)'),
                        ('term_2', 'Term II (May–Aug)'),
                        ('term_3', 'Term III (Sep–Dec)'),
                        ('annual', 'Annual'),
                    ],
                    max_length=20,
                )),
                ('description', models.TextField(blank=True)),
                ('badge_image', models.ImageField(blank=True, null=True, upload_to='group_badges/')),
                ('badge_color', models.CharField(default='#2563eb', max_length=7,
                                                  help_text='Fallback colour swatch used until a badge image is uploaded')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('classroom', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_groups',
                    to='students.classroom',
                )),
                ('subject', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='student_groups',
                    to='accounts.subject',
                    help_text='Optional — restrict grouping/ranking to one subject',
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_groups',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'student_groups',
                'ordering': ['classroom', 'name'],
                'unique_together': {('classroom', 'name', 'academic_year')},
            },
        ),
        migrations.CreateModel(
            name='GroupMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tier', models.CharField(
                    choices=[
                        ('very_strong', 'Very Strong'),
                        ('strong', 'Strong'),
                        ('average', 'Average'),
                        ('weak', 'Weak'),
                        ('unrated', 'Not Yet Rated'),
                    ],
                    default='unrated',
                    max_length=20,
                )),
                ('average_at_placement', models.FloatField(
                    blank=True, null=True,
                    help_text="Student's average % when placed, for reference",
                )),
                ('is_anchor', models.BooleanField(
                    default=False,
                    help_text="True if this student is one of the group's designated strong/very-strong anchors",
                )),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='memberships',
                    to='groups.studentgroup',
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='group_memberships',
                    to='students.studentprofile',
                )),
            ],
            options={
                'db_table': 'group_memberships',
                'ordering': ['-average_at_placement'],
                'unique_together': {('group', 'student')},
            },
        ),
        migrations.CreateModel(
            name='GroupTransferLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('warnings', models.TextField(blank=True,
                                               help_text='Balance warnings noted at transfer time, semicolon-separated')),
                ('transferred_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='group_transfers',
                    to='students.studentprofile',
                )),
                ('from_group', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='transfers_out',
                    to='groups.studentgroup',
                )),
                ('to_group', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='transfers_in',
                    to='groups.studentgroup',
                )),
                ('transferred_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='group_transfers_made',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'group_transfer_logs',
                'ordering': ['-transferred_at'],
            },
        ),
    ]
