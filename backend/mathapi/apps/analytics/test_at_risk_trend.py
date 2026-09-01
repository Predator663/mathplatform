"""
Tests for the at-risk 'trend' classification and filter added on top of
get_at_risk_students() — declining / stable / improving, based on the
newest vs. oldest of a student's up-to-3 most recent exam scores.

Also covers reports.AtRiskPDFView and pdf_engine.generate_at_risk_pdf, which
this same change fixed (the function previously fell off the end without
ever building/returning the PDF — see the missing tbl.setStyle/story.append
/doc.build/return that used to sit after the row-colouring loop).

Run with: python manage.py test mathapi.apps.analytics.test_at_risk_trend -v 2
"""
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import Exam, ExamScore
from mathapi.apps.analytics import services

User = get_user_model()


class AtRiskTrendFixtureBase(TestCase):
    """
    Three students, three exams each (oldest -> newest), engineered so each
    lands in exactly one trend bucket while all three stay 'at risk'
    (avg < threshold=50 for two of them; the declining student's own drop
    already qualifies her regardless of average):
      - declining: 55 -> 50 -> 30   (newest 30 is 20+ below oldest 55)
      - stable:    42 -> 45 -> 40   (newest 40 is within 10 of oldest 42)
      - improving: 25 -> 33 -> 45   (newest 45 is 20+ above oldest 25)
    """
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Trend Maths', code='TRND')
        cls.grade = GradeLevel.objects.create(name='TF2', short_name='TF2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='Trend Class', grade_level=cls.grade,
                                                  stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='trend_teacher@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher, subject=cls.subject, classroom=cls.classroom)

        cls.exams = []
        for i, date in enumerate([datetime.date(2026, 1, 1), datetime.date(2026, 2, 1), datetime.date(2026, 3, 1)]):
            exam = Exam.objects.create(
                title=f'Trend Exam {i + 1}', exam_type='monthly_test', term='term_1', academic_year='2026',
                exam_date=date, max_score=100, passing_score=40,
                subject=cls.subject, created_by=cls.teacher, is_published=True,
            )
            exam.classrooms.add(cls.classroom)
            cls.exams.append(exam)

        def make_student(tag, scores_oldest_to_newest):
            u = User.objects.create_user(email=f'{tag}@test.tz', password='x', role='student',
                                          first_name=tag.capitalize(), last_name='Student')
            sp = StudentProfile.objects.create(user=u, student_id=f'T{tag[:3].upper()}', classroom=cls.classroom)
            for exam, score in zip(cls.exams, scores_oldest_to_newest):
                ExamScore.objects.create(exam=exam, student=sp, score=score, entered_by=cls.teacher)
            return sp

        cls.declining_student = make_student('declining', [55, 50, 30])
        cls.stable_student = make_student('stable', [42, 45, 40])
        cls.improving_student = make_student('improving', [25, 33, 45])


class AtRiskTrendServiceTests(AtRiskTrendFixtureBase):
    def test_each_student_gets_the_expected_trend(self):
        results = {r['student_id']: r for r in services.get_at_risk_students(threshold=50)}
        self.assertEqual(results[self.declining_student.id]['trend'], 'declining')
        self.assertEqual(results[self.stable_student.id]['trend'], 'stable')
        self.assertEqual(results[self.improving_student.id]['trend'], 'improving')

    def test_declining_flag_still_matches_trend_for_backward_compatibility(self):
        results = {r['student_id']: r for r in services.get_at_risk_students(threshold=50)}
        self.assertTrue(results[self.declining_student.id]['flags']['declining'])
        self.assertFalse(results[self.stable_student.id]['flags']['declining'])
        self.assertFalse(results[self.improving_student.id]['flags']['declining'])

    def test_trend_filter_narrows_to_one_bucket(self):
        declining_only = services.get_at_risk_students(threshold=50, trend='declining')
        self.assertEqual({r['student_id'] for r in declining_only}, {self.declining_student.id})

        improving_only = services.get_at_risk_students(threshold=50, trend='improving')
        self.assertEqual({r['student_id'] for r in improving_only}, {self.improving_student.id})

        stable_only = services.get_at_risk_students(threshold=50, trend='stable')
        self.assertEqual({r['student_id'] for r in stable_only}, {self.stable_student.id})

    def test_no_trend_filter_returns_everyone_still_flagged(self):
        all_flagged = services.get_at_risk_students(threshold=50)
        sids = {r['student_id'] for r in all_flagged}
        self.assertEqual(sids, {self.declining_student.id, self.stable_student.id, self.improving_student.id})

    def test_single_score_student_defaults_to_stable(self):
        exam = Exam.objects.create(
            title='Solo Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 4, 1), max_score=100, passing_score=40,
            subject=self.subject, created_by=self.teacher, is_published=True,
        )
        exam.classrooms.add(self.classroom)
        u = User.objects.create_user(email='solo@test.tz', password='x', role='student', first_name='Solo', last_name='Student')
        sp = StudentProfile.objects.create(user=u, student_id='TSOLO', classroom=self.classroom)
        ExamScore.objects.create(exam=exam, student=sp, score=20, entered_by=self.teacher)  # well below threshold

        results = {r['student_id']: r for r in services.get_at_risk_students(threshold=50)}
        self.assertEqual(results[sp.id]['trend'], 'stable')


class AtRiskTrendAPITests(AtRiskTrendFixtureBase, APITestCase):
    def test_analytics_endpoint_accepts_trend_param(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/analytics/at-risk/', {'threshold': 50, 'trend': 'improving'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['at_risk'][0]['student_id'], self.improving_student.id)

    def test_analytics_endpoint_ignores_invalid_trend_value(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/analytics/at-risk/', {'threshold': 50, 'trend': 'sideways'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 3)  # falls back to no filter rather than erroring


class AtRiskPDFExportTests(AtRiskTrendFixtureBase, APITestCase):
    """Regression coverage for the export endpoint — generate_at_risk_pdf()
    previously never returned bytes at all (see module docstring)."""

    def test_pdf_export_succeeds_and_returns_a_pdf(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/reports/export/at-risk/pdf/', {'threshold': 50})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        content = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertGreater(len(content), 500)

    def test_pdf_export_with_trend_filter_succeeds(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/reports/export/at-risk/pdf/', {'threshold': 50, 'trend': 'declining'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(content.startswith(b'%PDF'))

    def test_pdf_export_with_no_matches_still_succeeds(self):
        # Nobody in this fixture is 'stable' *and* below a threshold of 0,
        # so this exercises the empty-rows branch of generate_at_risk_pdf.
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/reports/export/at-risk/pdf/', {'threshold': 0, 'trend': 'stable'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(content.startswith(b'%PDF'))
