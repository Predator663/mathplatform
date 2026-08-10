"""
Regression tests for scoping on POST /api/notifications/send-analytics-report/.

Every other analytics/report endpoint in this codebase enforces that a
teacher can only see data for classrooms/students they're actually assigned
to, via mathapi.apps.accounts.scoping (assert_classroom_owned /
get_teacher_classrooms) or analytics._check_student_access. This endpoint
originally bypassed that entirely — see send_analytics_report() in
services.py for the fix — because it resolved classroom_id/student_id with
a bare `.objects.filter(id=...).first()` and emailed the resulting report
to arbitrary external addresses regardless of who was asking.

Run with: python manage.py test mathapi.apps.notifications.test_report_scoping -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import Exam, ExamScore

User = get_user_model()


class SendAnalyticsReportScopingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Scoping Maths', code='SCPM')
        cls.grade = GradeLevel.objects.create(name='Form 4', short_name='F4', education_level='secondary', order=4)

        cls.admin = User.objects.create_user(email='admin@scoping.tz', password='x', role='super_admin')

        # Teacher A has NO assignment to this classroom/student.
        cls.teacher_a = User.objects.create_user(email='teacher_a@scoping.tz', password='x', role='teacher')

        # Teacher B IS assigned to it.
        cls.teacher_b = User.objects.create_user(email='teacher_b@scoping.tz', password='x', role='teacher')

        cls.classroom = Classroom.objects.create(
            name="Teacher B's Class", grade_level=cls.grade, stream='general', academic_year='2026',
        )
        TeacherAssignment.objects.create(teacher=cls.teacher_b, subject=cls.subject, classroom=cls.classroom)

        student_user = User.objects.create_user(
            email='student_secret@scoping.tz', password='x', role='student',
            first_name='Secret', last_name='Student',
        )
        cls.student = StudentProfile.objects.create(
            user=student_user, student_id='SEC001', classroom=cls.classroom,
        )

        exam = Exam.objects.create(
            title='Confidential Exam', exam_type='mid_term', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 5, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher_b, is_published=True,
        )
        exam.classrooms.add(cls.classroom)
        ExamScore.objects.create(exam=exam, student=cls.student, score=42)

    def _post(self, user, **payload):
        self.client.force_authenticate(user)
        return self.client.post('/api/notifications/send-analytics-report/', {
            'recipients': ['someone@external.example.com'],
            **payload,
        }, format='json')

    # ── Unauthorized teacher: must be blocked ──────────────────────────────
    def test_unassigned_teacher_cannot_email_student_report(self):
        resp = self._post(self.teacher_a, report_type='student', student_id=self.student.id)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unassigned_teacher_cannot_email_class_report(self):
        resp = self._post(self.teacher_a, report_type='class', classroom_id=self.classroom.id)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unassigned_teacher_cannot_email_at_risk_report_for_classroom(self):
        resp = self._post(self.teacher_a, report_type='at-risk', classroom_id=self.classroom.id)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ── Authorized teacher: still works ─────────────────────────────────────
    def test_assigned_teacher_can_email_student_report(self):
        resp = self._post(self.teacher_b, report_type='student', student_id=self.student.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('sent'))

    def test_assigned_teacher_can_email_class_report(self):
        resp = self._post(self.teacher_b, report_type='class', classroom_id=self.classroom.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('sent'))

    def test_teacher_overview_report_is_scoped_not_platform_wide(self):
        """A teacher's 'overview' report should not error, and should be
        scoped to their own classrooms rather than the whole platform."""
        resp = self._post(self.teacher_a, report_type='overview')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('sent'))

    # ── Admin: unrestricted, as before ──────────────────────────────────────
    def test_admin_can_email_any_student_report(self):
        resp = self._post(self.admin, report_type='student', student_id=self.student.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('sent'))

    def test_admin_can_email_platform_overview(self):
        resp = self._post(self.admin, report_type='overview')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data.get('sent'))
