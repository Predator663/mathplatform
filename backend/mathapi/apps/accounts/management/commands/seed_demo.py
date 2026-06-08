"""
Management command: python manage.py seed_demo
Seeds the database with realistic Tanzania curriculum demo data.
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import MathTopic, Exam, ExamTopicWeight, ExamScore, TopicScore

User = get_user_model()

# ── Tanzania O-Level Math Topics ───────────────────────────────────────────────
OLEVEL_TOPICS = [
    ('Numbers & Operations',   '#6366f1', 'o_level'),
    ('Algebra',                '#f59e0b', 'o_level'),
    ('Geometry',               '#10b981', 'o_level'),
    ('Trigonometry',           '#3b82f6', 'o_level'),
    ('Statistics',             '#ec4899', 'o_level'),
    ('Vectors',                '#8b5cf6', 'o_level'),
    ('Coordinate Geometry',    '#06b6d4', 'o_level'),
    ('Matrices & Transformations', '#f97316', 'o_level'),
]

# ── Tanzania Primary Math Topics ───────────────────────────────────────────────
PRIMARY_TOPICS = [
    ('Nambari (Numbers)',       '#6366f1', 'primary'),
    ('Maumbo (Shapes)',         '#10b981', 'primary'),
    ('Kipimo (Measurement)',    '#f59e0b', 'primary'),
    ('Takwimu (Statistics)',    '#3b82f6', 'primary'),
    ('Sehemu (Fractions)',      '#ec4899', 'primary'),
]

STUDENT_NAMES = [
    ('Amina',  'Juma'),    ('Baraka', 'Mwangi'),  ('Cecilia', 'Osei'),
    ('Daniel', 'Kamau'),   ('Esther', 'Nkosi'),   ('Fadhili', 'Mushi'),
    ('Grace',  'Shayo'),   ('Hassan', 'Makame'),  ('Irene',   'Mganga'),
    ('Jonas',  'Msigwa'),  ('Khadija','Salum'),   ('Lazaro',  'Mwita'),
    ('Mary',   'Chacha'),  ('Ndugu',  'Kivuyo'),  ('Omary',   'Rashidi'),
    ('Pendo',  'Mrema'),   ('Qasim',  'Ally'),    ('Rose',    'Mhina'),
    ('Said',   'Mzee'),    ('Tumaini','Kweka'),
    ('Upendo', 'Mbwambo'), ('Venance','Nturanabo'),('Witness', 'Festo'),
    ('Xavery', 'Mwakasege'),('Yohana','Mnyampanda'),
]

REGIONS = ['Dar es Salaam', 'Arusha', 'Mwanza', 'Dodoma', 'Mbeya',
           'Morogoro', 'Tanga', 'Kilimanjaro', 'Iringa', 'Moshi']


class Command(BaseCommand):
    help = 'Seed database with Tanzania curriculum demo data'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Tanzania curriculum demo data...\n')

        # ── Users ──────────────────────────────────────────────────────────────
        admin, _ = User.objects.get_or_create(
            email='admin@mathplatform.edu',
            defaults={
                'first_name': 'System', 'last_name': 'Admin',
                'role': 'super_admin', 'is_staff': True, 'is_superuser': True,
            }
        )
        admin.set_password('admin123'); admin.save()

        teacher1, _ = User.objects.get_or_create(
            email='mwalimu.john@mathplatform.edu',
            defaults={'first_name': 'John', 'last_name': 'Mwalimu', 'role': 'teacher'}
        )
        teacher1.set_password('teacher123'); teacher1.save()

        teacher2, _ = User.objects.get_or_create(
            email='mwalimu.grace@mathplatform.edu',
            defaults={'first_name': 'Grace', 'last_name': 'Msangi', 'role': 'teacher'}
        )
        teacher2.set_password('teacher123'); teacher2.save()

        # ── Grade Levels (Tanzania Curriculum) ────────────────────────────────
        grade_levels_data = [
            # Pre-Primary
            ('PP1 — Darasa la Kwanza la Awali', 'PP1', 'pre_primary', 1, '', 'Hisabati ya Awali'),
            ('PP2 — Darasa la Pili la Awali',   'PP2', 'pre_primary', 2, '', 'Hisabati ya Awali'),
            # Primary
            ('Standard 1', 'Std 1', 'primary', 3,  '', 'Hisabati'),
            ('Standard 2', 'Std 2', 'primary', 4,  '', 'Hisabati'),
            ('Standard 3', 'Std 3', 'primary', 5,  '', 'Hisabati'),
            ('Standard 4', 'Std 4', 'primary', 6,  '', 'Hisabati'),
            ('Standard 5', 'Std 5', 'primary', 7,  '', 'Hisabati'),
            ('Standard 6', 'Std 6', 'primary', 8,  '', 'Hisabati'),
            ('Standard 7', 'Std 7', 'primary', 9,  'PSLE', 'Hisabati'),
            # O-Level
            ('Form 1', 'Form 1', 'o_level', 10, '',     'Mathematics'),
            ('Form 2', 'Form 2', 'o_level', 11, '',     'Mathematics'),
            ('Form 3', 'Form 3', 'o_level', 12, '',     'Mathematics'),
            ('Form 4', 'Form 4', 'o_level', 13, 'CSEE', 'Mathematics'),
            # A-Level
            ('Form 5', 'Form 5', 'a_level', 14, '',      'Advanced Mathematics / BAM'),
            ('Form 6', 'Form 6', 'a_level', 15, 'ACSEE', 'Advanced Mathematics / BAM'),
        ]
        grade_objs = {}
        for name, short, level, order, necta, math_subj in grade_levels_data:
            gl, _ = GradeLevel.objects.get_or_create(
                name=name,
                defaults={
                    'short_name':      short,
                    'education_level': level,
                    'order':           order,
                    'necta_exam':      necta,
                    'math_subject':    math_subj,
                }
            )
            grade_objs[name] = gl
        self.stdout.write(f'  ✓ {len(grade_objs)} grade levels')

        # ── Classrooms ────────────────────────────────────────────────────────
        form2a, _ = Classroom.objects.get_or_create(
            name='Form 2A', grade_level=grade_objs['Form 2'], academic_year='2024',
            defaults={'stream': 'general', 'is_active': True}
        )
        form2a.teachers.add(teacher1)

        form2b, _ = Classroom.objects.get_or_create(
            name='Form 2B', grade_level=grade_objs['Form 2'], academic_year='2024',
            defaults={'stream': 'general', 'is_active': True}
        )
        form2b.teachers.add(teacher1)

        form3sci, _ = Classroom.objects.get_or_create(
            name='Form 3 Science', grade_level=grade_objs['Form 3'], academic_year='2024',
            defaults={'stream': 'science', 'is_active': True}
        )
        form3sci.teachers.add(teacher2)

        std7, _ = Classroom.objects.get_or_create(
            name='Standard 7A', grade_level=grade_objs['Standard 7'], academic_year='2024',
            defaults={'stream': 'general', 'is_active': True}
        )
        std7.teachers.add(teacher2)

        classrooms_map = [form2a, form2b, form3sci, std7]
        self.stdout.write(f'  ✓ {len(classrooms_map)} classrooms')

        # ── Math Topics ───────────────────────────────────────────────────────
        topic_objs = {}
        for i, (name, color, level) in enumerate(OLEVEL_TOPICS + PRIMARY_TOPICS):
            t, _ = MathTopic.objects.get_or_create(
                name=name,
                defaults={'color': color, 'level': level, 'order': i}
            )
            topic_objs[name] = t
        self.stdout.write(f'  ✓ {len(topic_objs)} math topics')

        # ── Students ──────────────────────────────────────────────────────────
        random.seed(42)
        student_profiles = []
        classrooms_for_students = [form2a] * 10 + [form2b] * 8 + [form3sci] * 4 + [std7] * 3
        for idx, (first, last) in enumerate(STUDENT_NAMES):
            email = f'{first.lower()}.{last.lower()}{idx}@student.mathplatform.edu'
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={'first_name': first, 'last_name': last, 'role': 'student'}
            )
            user.set_password('student123'); user.save()
            classroom = classrooms_for_students[idx] if idx < len(classrooms_for_students) else form2a
            profile, _ = StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    'student_id':   f'S{2024000 + idx + 1}',
                    'classroom':    classroom,
                    'date_of_birth': date(2009, random.randint(1, 12), random.randint(1, 28)),
                    'region':       random.choice(REGIONS),
                    'district':     'Urban',
                    'index_number': f'P{2024}{str(idx+1).zfill(4)}' if classroom == std7 else '',
                }
            )
            student_profiles.append(profile)
        self.stdout.write(f'  ✓ {len(student_profiles)} students')

        # ── Exams (2024 academic year, Tanzania terms) ────────────────────────
        olevel_topics_list = [topic_objs[n] for n, _, l in OLEVEL_TOPICS]
        primary_topics_list = [topic_objs[n] for n, _, l in PRIMARY_TOPICS]

        exam_configs = [
            # Form 2 exams
            ('Monthly Test — January',   'monthly_test', 'term_1', date(2024, 1, 26), 40,  20,  [form2a, form2b]),
            ('Mid-Term I Examination',   'mid_term',     'term_1', date(2024, 3, 8),  100, 30,  [form2a, form2b]),
            ('Terminal I Examination',   'terminal',     'term_1', date(2024, 4, 19), 100, 30,  [form2a, form2b]),
            ('Monthly Test — June',      'monthly_test', 'term_2', date(2024, 6, 7),  40,  20,  [form2a, form2b]),
            ('Mid-Term II Examination',  'mid_term',     'term_2', date(2024, 7, 12), 100, 30,  [form2a, form2b]),
            ('Terminal II Examination',  'terminal',     'term_2', date(2024, 8, 30), 100, 30,  [form2a, form2b]),
            ('Mock Examination',         'mock',         'term_3', date(2024, 10, 11),100, 30,  [form2a, form2b]),
            # Form 3 Science
            ('Mid-Term I — Form 3 Sci', 'mid_term',     'term_1', date(2024, 3, 8),  100, 30,  [form3sci]),
            ('Terminal I — Form 3 Sci', 'terminal',     'term_1', date(2024, 4, 19), 100, 30,  [form3sci]),
            # Standard 7
            ('Mid-Term I — Std 7',      'mid_term',     'term_1', date(2024, 3, 8),  100, 40,  [std7]),
            ('PSLE Mock — Std 7',       'mock',         'term_3', date(2024, 10, 4), 100, 40,  [std7]),
        ]

        exams = []
        for title, etype, term, edate, max_s, pass_s, cls_list in exam_configs:
            exam, _ = Exam.objects.get_or_create(
                title=title,
                academic_year='2024',
                defaults={
                    'exam_type':    etype,
                    'term':         term,
                    'exam_date':    edate,
                    'max_score':    max_s,
                    'passing_score': pass_s,
                    'created_by':   teacher1,
                    'is_published': True,
                }
            )
            exam.classrooms.set(cls_list)

            # Topic weights for 100-mark exams
            is_primary = any(c == std7 for c in cls_list)
            topics_pool = primary_topics_list if is_primary else olevel_topics_list
            if max_s == 100 and not exam.topic_weights.exists():
                selected = random.sample(topics_pool, min(4, len(topics_pool)))
                marks = [30, 25, 25, 20]
                for topic, m in zip(selected, marks):
                    ExamTopicWeight.objects.get_or_create(
                        exam=exam, topic=topic,
                        defaults={'max_marks': m, 'weight_percentage': m}
                    )
            exams.append(exam)

        self.stdout.write(f'  ✓ {len(exams)} exams')

        # ── Scores ────────────────────────────────────────────────────────────
        random.seed(99)
        score_count = 0
        for profile in student_profiles:
            ability = random.gauss(58, 15)
            ability = max(15, min(96, ability))
            improving = random.random() < 0.35

            for i, exam in enumerate(exams):
                # Only score exams for classrooms the student belongs to
                if profile.classroom not in exam.classrooms.all():
                    continue

                if random.random() < 0.04:
                    ExamScore.objects.get_or_create(
                        exam=exam, student=profile,
                        defaults={'score': 0, 'is_absent': True, 'entered_by': teacher1}
                    )
                    continue

                trend_boost = (i * 1.2) if improving else -(i * 0.4)
                noise = random.gauss(0, 9)
                pct = min(98, max(5, ability + trend_boost + noise))
                score = round((pct / 100) * float(exam.max_score), 1)

                exam_score, created = ExamScore.objects.get_or_create(
                    exam=exam, student=profile,
                    defaults={'score': score, 'entered_by': teacher1}
                )

                if created and exam.topic_weights.exists():
                    for tw in exam.topic_weights.all():
                        topic_noise = random.gauss(0, 12)
                        tpct = min(100, max(0, pct + topic_noise))
                        tscore = round((tpct / 100) * float(tw.max_marks), 1)
                        TopicScore.objects.get_or_create(
                            exam_score=exam_score, topic=tw.topic,
                            defaults={'score': tscore, 'max_marks': tw.max_marks}
                        )
                score_count += 1

        self.stdout.write(f'  ✓ ~{score_count} scores generated')

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Tanzania curriculum demo data ready!\n'
            f'\n  Login credentials:\n'
            f'  Admin   : admin@mathplatform.edu        / admin123\n'
            f'  Teacher1: mwalimu.john@mathplatform.edu / teacher123\n'
            f'  Teacher2: mwalimu.grace@mathplatform.edu/ teacher123\n'
            f'  Students: (any student email)            / student123\n'
            f'\n  Classrooms: Form 2A, Form 2B, Form 3 Science, Standard 7A\n'
            f'  Grades: PP1–PP2, Std 1–7, Form 1–4, Form 5–6\n'
        ))
