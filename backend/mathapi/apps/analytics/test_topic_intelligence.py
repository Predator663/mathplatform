"""
Tests for topic_intelligence_services + its API views. Verified against
hand-computed expected values.
Run with: python manage.py test mathapi.apps.analytics.test_topic_intelligence -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import MathTopic, Exam, ExamScore, ExamTopicWeight, TopicScore
from mathapi.apps.quizzes.models import DailyQuiz, DailyQuizScore
from . import topic_intelligence_services as tis

User = get_user_model()


class TopicIntelligenceServiceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='TI Maths', code='TIM')
        cls.grade = GradeLevel.objects.create(name='F3', short_name='F3', education_level='secondary', order=3)
        cls.classroom_a = Classroom.objects.create(name='TIA', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.classroom_b = Classroom.objects.create(name='TIB', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.topic_hard = MathTopic.objects.create(subject=cls.subject, name='Calculus')
        cls.topic_easy = MathTopic.objects.create(subject=cls.subject, name='Basic Arithmetic')

        cls.teacher = User.objects.create_user(email='ti_teacher@test.tz', password='x', role='teacher')

        cls.s_a = StudentProfile.objects.create(
            user=User.objects.create_user(email='ti_sa@test.tz', password='x', role='student'),
            student_id='TIA1', classroom=cls.classroom_a,
        )
        cls.s_b = StudentProfile.objects.create(
            user=User.objects.create_user(email='ti_sb@test.tz', password='x', role='student'),
            student_id='TIB1', classroom=cls.classroom_b,
        )

        # Classroom A does poorly on Calculus (30%), classroom B does well (90%)
        exam_a = Exam.objects.create(
            title='TI Exam A', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 1, 1), max_score=100, passing_score=30,
            subject=cls.subject, is_published=True, created_by=cls.teacher,
        )
        exam_a.classrooms.add(cls.classroom_a, cls.classroom_b)
        ExamTopicWeight.objects.create(exam=exam_a, topic=cls.topic_hard, max_marks=50, weight_percentage=50)

        es_a = ExamScore.objects.create(exam=exam_a, student=cls.s_a, score=40)
        TopicScore.objects.create(exam_score=es_a, topic=cls.topic_hard, score=15, max_marks=50)  # 30%

        es_b = ExamScore.objects.create(exam=exam_a, student=cls.s_b, score=90)
        TopicScore.objects.create(exam_score=es_b, topic=cls.topic_hard, score=45, max_marks=50)  # 90%

        # Basic Arithmetic: both students do well (85%, 95%) via daily quizzes
        quiz1 = DailyQuiz.objects.create(
            date=datetime.date(2026, 1, 5), classroom=cls.classroom_a, subject=cls.subject,
            topic=cls.topic_easy, term='term_1', academic_year='2026',
            max_score=20, passing_score=10, created_by=cls.teacher,
        )
        DailyQuizScore.objects.create(quiz=quiz1, student=cls.s_a, score=17, entered_by=cls.teacher)  # 85%

        quiz2 = DailyQuiz.objects.create(
            date=datetime.date(2026, 1, 6), classroom=cls.classroom_b, subject=cls.subject,
            topic=cls.topic_easy, term='term_1', academic_year='2026',
            max_score=20, passing_score=10, created_by=cls.teacher,
        )
        DailyQuizScore.objects.create(quiz=quiz2, student=cls.s_b, score=19, entered_by=cls.teacher)  # 95%

    def test_overview_ranks_hardest_topic_first(self):
        data = tis.get_topic_intelligence_overview()
        self.assertEqual(data['topics'][0]['topic_name'], 'Calculus')
        self.assertEqual(data['topics'][0]['average'], round((30 + 90) / 2, 1))
        self.assertEqual(data['topics'][0]['difficulty_rank'], 1)
        self.assertEqual(data['topics'][1]['topic_name'], 'Basic Arithmetic')

    def test_overview_combines_exam_and_quiz_data(self):
        data = tis.get_topic_intelligence_overview()
        arithmetic = next(t for t in data['topics'] if t['topic_name'] == 'Basic Arithmetic')
        self.assertEqual(arithmetic['attempts'], 2)  # both from quizzes
        self.assertEqual(arithmetic['average'], round((85 + 95) / 2, 1))

    def test_overview_excludes_quizzes_when_disabled(self):
        data = tis.get_topic_intelligence_overview(include_quizzes=False)
        names = {t['topic_name'] for t in data['topics']}
        self.assertNotIn('Basic Arithmetic', names)  # only exists via quiz data
        self.assertIn('Calculus', names)

    def test_classroom_matrix_shows_per_classroom_averages(self):
        data = tis.get_topic_intelligence_overview()
        matrix = data['classroom_matrix']
        classroom_names = [c['name'] for c in matrix['classrooms']]
        topic_names = [t['name'] for t in matrix['topics']]
        self.assertIn('TIA', classroom_names)
        self.assertIn('TIB', classroom_names)

        a_idx = classroom_names.index('TIA')
        calc_idx = topic_names.index('Calculus')
        self.assertEqual(matrix['matrix'][a_idx][calc_idx], 30.0)

        b_idx = classroom_names.index('TIB')
        self.assertEqual(matrix['matrix'][b_idx][calc_idx], 90.0)

    def test_classroom_filter_narrows_scope(self):
        data = tis.get_topic_intelligence_overview(classroom_ids=[self.classroom_a.id])
        calc = next(t for t in data['topics'] if t['topic_name'] == 'Calculus')
        self.assertEqual(calc['attempts'], 1)
        self.assertEqual(calc['average'], 30.0)

    def test_empty_scope_returns_empty_structure_not_error(self):
        empty_classroom = Classroom.objects.create(name='TIEmpty', grade_level=self.grade, stream='general', academic_year='2026')
        data = tis.get_topic_intelligence_overview(classroom_ids=[empty_classroom.id])
        self.assertEqual(data['topics'], [])
        self.assertEqual(data['classroom_matrix']['matrix'], [])


class TopicDistributionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Dist Maths', code='DSTM')
        cls.grade = GradeLevel.objects.create(name='F4', short_name='F4', education_level='secondary', order=4)
        cls.classroom = Classroom.objects.create(name='DIST1', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.topic = MathTopic.objects.create(subject=cls.subject, name='Statistics')
        cls.teacher = User.objects.create_user(email='dist_teacher@test.tz', password='x', role='teacher')

        # 3 students with averages 15%, 55%, 95% -> one in each of 3 different buckets
        for i, pct in enumerate([15, 55, 95]):
            student = StudentProfile.objects.create(
                user=User.objects.create_user(email=f'dist_s{i}@test.tz', password='x', role='student'),
                student_id=f'DIST{i}', classroom=cls.classroom,
            )
            quiz = DailyQuiz.objects.create(
                date=datetime.date(2026, 2, i + 1), classroom=cls.classroom, subject=cls.subject,
                topic=cls.topic, term='term_1', academic_year='2026',
                max_score=100, passing_score=30, created_by=cls.teacher,
            )
            DailyQuizScore.objects.create(quiz=quiz, student=student, score=pct, entered_by=cls.teacher)

    def test_histogram_buckets_student_averages_correctly(self):
        data = tis.get_topic_distribution(self.topic.id)
        counts = {h['range']: h['count'] for h in data['histogram']}
        self.assertEqual(counts['0-20%'], 1)
        self.assertEqual(counts['40-60%'], 1)
        self.assertEqual(counts['80-100%'], 1)
        self.assertEqual(counts['20-40%'], 0)

    def test_timeline_chronological(self):
        data = tis.get_topic_distribution(self.topic.id)
        dates = [t['date'] for t in data['timeline']]
        self.assertEqual(dates, sorted(dates))

    def test_missing_topic_returns_empty_not_error(self):
        data = tis.get_topic_distribution(999999)
        self.assertEqual(data['histogram'], [])
        self.assertIsNone(data['summary'])


class TopicIntelligenceViewScopingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Scope TI Maths', code='STIM')
        cls.grade = GradeLevel.objects.create(name='F1', short_name='F1', education_level='secondary', order=1)
        cls.classroom_a = Classroom.objects.create(name='STIA', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.classroom_b = Classroom.objects.create(name='STIB', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.admin = User.objects.create_user(email='sti_admin@test.tz', password='x', role='super_admin')
        cls.teacher_a = User.objects.create_user(email='sti_teacher_a@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_a, subject=cls.subject, classroom=cls.classroom_a)

        cls.topic = MathTopic.objects.create(subject=cls.subject, name='Probability')

        student = StudentProfile.objects.create(
            user=User.objects.create_user(email='sti_student@test.tz', password='x', role='student'),
            student_id='STI001', classroom=cls.classroom_b,
        )
        quiz = DailyQuiz.objects.create(
            date=datetime.date(2026, 1, 1), classroom=cls.classroom_b, subject=cls.subject,
            topic=cls.topic, term='term_1', academic_year='2026',
            max_score=10, passing_score=5, created_by=cls.admin,
        )
        DailyQuizScore.objects.create(quiz=quiz, student=student, score=7, entered_by=cls.admin)

    def test_teacher_blocked_from_viewing_unassigned_classroom(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get('/api/analytics/topics/overview/', {'classroom_id': self.classroom_b.id})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_scoped_to_own_classrooms_by_default(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get('/api/analytics/topics/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # teacher_a has no data in their own classroom (all data is in classroom_b)
        self.assertEqual(resp.data['topics'], [])

    def test_admin_sees_all_classrooms(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/analytics/topics/overview/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['topics']), 1)

    def test_student_cannot_access_topic_intelligence(self):
        student_user = User.objects.get(email='sti_student@test.tz')
        self.client.force_authenticate(student_user)
        resp = self.client.get('/api/analytics/topics/overview/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_distribution_endpoint_respects_scope(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/analytics/topics/{self.topic.id}/distribution/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp.data['summary'])  # no data in teacher_a's own classroom
