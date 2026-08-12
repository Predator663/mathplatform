"""
Tests for quizzes.analytics_services — verified against hand-computed
expected values so a subtly wrong aggregation doesn't slip through.
Run with: python manage.py test mathapi.apps.quizzes.test_analytics -v 2
"""
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import MathTopic
from .models import DailyQuiz, DailyQuizScore
from . import analytics_services

User = get_user_model()


class ClassroomQuizAnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Analytics Maths', code='ANQZ')
        cls.grade = GradeLevel.objects.create(name='Form 1', short_name='F1', education_level='secondary', order=1)
        cls.classroom = Classroom.objects.create(name='1F', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.topic_fractions = MathTopic.objects.create(subject=cls.subject, name='Fractions')
        cls.topic_algebra = MathTopic.objects.create(subject=cls.subject, name='Algebra')

        cls.teacher = User.objects.create_user(email='an_teacher@test.tz', password='x', role='teacher')

        cls.s1 = StudentProfile.objects.create(
            user=User.objects.create_user(email='an_s1@test.tz', password='x', role='student'),
            student_id='AN001', classroom=cls.classroom,
        )
        cls.s2 = StudentProfile.objects.create(
            user=User.objects.create_user(email='an_s2@test.tz', password='x', role='student'),
            student_id='AN002', classroom=cls.classroom,
        )

        # Quiz 1: Fractions, max 10 — s1 scores 8 (80%), s2 scores 4 (40%)
        cls.quiz1 = DailyQuiz.objects.create(
            date=datetime.date(2026, 2, 1), classroom=cls.classroom, subject=cls.subject,
            topic=cls.topic_fractions, term='term_1', academic_year='2026',
            max_score=10, passing_score=5, created_by=cls.teacher,
        )
        DailyQuizScore.objects.create(quiz=cls.quiz1, student=cls.s1, score=8, entered_by=cls.teacher)
        DailyQuizScore.objects.create(quiz=cls.quiz1, student=cls.s2, score=4, entered_by=cls.teacher)

        # Quiz 2: Algebra, max 20 — s1 scores 10 (50%), s2 absent
        cls.quiz2 = DailyQuiz.objects.create(
            date=datetime.date(2026, 2, 2), classroom=cls.classroom, subject=cls.subject,
            topic=cls.topic_algebra, term='term_1', academic_year='2026',
            max_score=20, passing_score=10, created_by=cls.teacher,
        )
        DailyQuizScore.objects.create(quiz=cls.quiz2, student=cls.s1, score=10, entered_by=cls.teacher)
        DailyQuizScore.objects.create(quiz=cls.quiz2, student=cls.s2, score=0, is_absent=True, entered_by=cls.teacher)

    def test_overview_counts(self):
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id)
        overview = data['overview']
        self.assertEqual(overview['quiz_count'], 2)
        self.assertEqual(overview['scores_entered'], 4)  # 2+2, including the absence
        self.assertEqual(overview['present_count'], 3)   # 4 total minus 1 absence
        self.assertEqual(overview['absent_count'], 1)

    def test_overview_average_is_mean_of_present_percentages(self):
        # Present percentages: 80, 40, 50 -> mean = 56.7
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id)
        self.assertEqual(data['overview']['average_score'], round((80 + 40 + 50) / 3, 1))

    def test_overview_pass_rate(self):
        # Passing: s1@8/10 (pass, >=5), s2@4/10 (fail, <5), s1@10/20 (pass, >=10)
        # 2 out of 3 present scores passed
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id)
        self.assertEqual(data['overview']['pass_rate'], round(2 / 3 * 100, 1))

    def test_trend_has_one_point_per_quiz_date(self):
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id)
        trend = data['trend']
        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[0]['date'], '2026-02-01')
        self.assertEqual(trend[0]['average'], round((80 + 40) / 2, 1))
        self.assertEqual(trend[1]['date'], '2026-02-02')
        # Only s1 present on quiz 2 -> average is exactly their score
        self.assertEqual(trend[1]['average'], 50.0)

    def test_topic_breakdown_separates_topics_correctly(self):
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id)
        by_name = {t['topic_name']: t for t in data['topic_breakdown']}
        self.assertIn('Fractions', by_name)
        self.assertIn('Algebra', by_name)
        self.assertEqual(by_name['Fractions']['attempts'], 2)
        self.assertEqual(by_name['Fractions']['average'], round((80 + 40) / 2, 1))
        # Algebra only has 1 present score (s2 was absent)
        self.assertEqual(by_name['Algebra']['attempts'], 1)
        self.assertEqual(by_name['Algebra']['average'], 50.0)

    def test_topic_filter_narrows_results(self):
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id, topic_id=self.topic_fractions.id)
        self.assertEqual(data['overview']['quiz_count'], 1)
        self.assertEqual(len(data['topic_breakdown']), 1)
        self.assertEqual(data['topic_breakdown'][0]['topic_name'], 'Fractions')

    def test_at_risk_and_top_students(self):
        # s1 average: (80+50)/2 = 65; s2 average: 40 (only 1 present score)
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id, at_risk_threshold=50)
        at_risk_ids = {r['student_id'] for r in data['at_risk_students']}
        self.assertIn(self.s2.id, at_risk_ids)
        self.assertNotIn(self.s1.id, at_risk_ids)
        self.assertEqual(data['top_students'][0]['student_id'], self.s1.id)

    def test_soft_deleted_quiz_excluded(self):
        self.quiz2.is_deleted = True
        self.quiz2.save()
        data = analytics_services.get_classroom_quiz_analytics(self.classroom.id)
        self.assertEqual(data['overview']['quiz_count'], 1)

    def test_empty_classroom_returns_none_not_error(self):
        empty_classroom = Classroom.objects.create(name='Empty', grade_level=self.grade, stream='general', academic_year='2026')
        data = analytics_services.get_classroom_quiz_analytics(empty_classroom.id)
        self.assertEqual(data['overview']['quiz_count'], 0)
        self.assertIsNone(data['overview']['average_score'])
        self.assertIsNone(data['overview']['pass_rate'])
        self.assertEqual(data['trend'], [])
        self.assertEqual(data['topic_breakdown'], [])


class StudentQuizTopicProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Progress Quiz Maths', code='PGQZ')
        cls.grade = GradeLevel.objects.create(name='Form 3', short_name='F3', education_level='secondary', order=3)
        cls.classroom = Classroom.objects.create(name='3B', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.topic = MathTopic.objects.create(subject=cls.subject, name='Geometry')
        cls.teacher = User.objects.create_user(email='pq_teacher@test.tz', password='x', role='teacher')
        cls.student = StudentProfile.objects.create(
            user=User.objects.create_user(email='pq_student@test.tz', password='x', role='student'),
            student_id='PQ001', classroom=cls.classroom,
        )

        for i, score in enumerate([5, 7, 10]):  # out of 10 -> 50%, 70%, 100%
            quiz = DailyQuiz.objects.create(
                date=datetime.date(2026, 1, i + 1), classroom=cls.classroom, subject=cls.subject,
                topic=cls.topic, term='term_1', academic_year='2026',
                max_score=10, passing_score=5, created_by=cls.teacher,
            )
            DailyQuizScore.objects.create(quiz=quiz, student=cls.student, score=score, entered_by=cls.teacher)

    def test_summary_stats(self):
        data = analytics_services.get_student_quiz_topic_progress(self.student.id)
        summary = data['summary']
        self.assertEqual(summary['quizzes_taken'], 3)
        self.assertEqual(summary['average'], round((50 + 70 + 100) / 3, 1))
        self.assertEqual(summary['highest'], 100.0)
        self.assertEqual(summary['lowest'], 50.0)
        self.assertEqual(summary['trend'], 'improving')  # strictly increasing scores

    def test_timeline_is_chronological(self):
        data = analytics_services.get_student_quiz_topic_progress(self.student.id)
        dates = [t['exam_date'] for t in data['timeline']]
        self.assertEqual(dates, sorted(dates))

    def test_topic_data_present(self):
        data = analytics_services.get_student_quiz_topic_progress(self.student.id)
        self.assertEqual(len(data['topic_data']), 1)
        self.assertEqual(data['topic_data'][0]['topic_name'], 'Geometry')
        self.assertEqual(data['topic_data'][0]['attempts'], 3)
