"""
Tests for WhatsApp result delivery (console backend — no real Twilio
credentials needed; see notifications/whatsapp.py).
Run with: python manage.py test mathapi.apps.notifications.test_whatsapp -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile, ParentStudentLink
from mathapi.apps.exams.models import Exam, ExamScore
from .models import NotificationLog
from . import whatsapp

User = get_user_model()


class WhatsAppProviderTests(APITestCase):
    def test_normalizes_common_phone_formats(self):
        self.assertEqual(whatsapp._normalize_phone('+255 700 000 000'), '+255700000000')
        self.assertEqual(whatsapp._normalize_phone('0700-000-000'), '+0700000000')

    def test_rejects_garbage_input(self):
        self.assertIsNone(whatsapp._normalize_phone('not a phone'))
        self.assertIsNone(whatsapp._normalize_phone(''))

    def test_console_fallback_reports_success_without_credentials(self):
        # settings.TWILIO_ACCOUNT_SID is unset in tests -> console backend.
        self.assertFalse(whatsapp.is_configured())
        ok, error = whatsapp.send_whatsapp_message('+255700000000', 'Test message')
        self.assertTrue(ok)
        self.assertEqual(error, '')

    def test_invalid_phone_fails_cleanly(self):
        ok, error = whatsapp.send_whatsapp_message('garbage', 'Test message')
        self.assertFalse(ok)
        self.assertIn('not a valid phone number', error)


class SendWhatsAppResultViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='WA Maths', code='WAMM')
        cls.grade = GradeLevel.objects.create(name='Form 1', short_name='F1', education_level='secondary', order=1)
        cls.classroom = Classroom.objects.create(name='1A', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.teacher_a = User.objects.create_user(email='wa_teacher_a@test.tz', password='x', role='teacher')
        cls.teacher_b = User.objects.create_user(email='wa_teacher_b@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_b, subject=cls.subject, classroom=cls.classroom)

        student_user = User.objects.create_user(email='wa_student@test.tz', password='x', role='student')
        cls.student = StudentProfile.objects.create(user=student_user, student_id='WA001', classroom=cls.classroom)

        parent_user = User.objects.create_user(email='wa_parent@test.tz', password='x', role='parent', phone='+255700111222')
        ParentStudentLink.objects.create(parent=parent_user, student=cls.student, is_primary=True)

        cls.exam = Exam.objects.create(
            title='WA Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=30,
            subject=cls.subject, is_published=True,
        )
        cls.exam.classrooms.add(cls.classroom)
        ExamScore.objects.create(exam=cls.exam, student=cls.student, score=72)

    def test_assigned_teacher_can_send_result(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.post('/api/notifications/send-whatsapp-result/', {
            'student_id': self.student.id, 'exam_id': self.exam.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['sent'])
        self.assertEqual(resp.data['recipient_count'], 1)
        log = NotificationLog.objects.filter(recipient__email='wa_parent@test.tz').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.channel, NotificationLog.Channel.WHATSAPP)
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_unassigned_teacher_is_blocked(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.post('/api/notifications/send-whatsapp-result/', {
            'student_id': self.student.id, 'exam_id': self.exam.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_falls_back_to_student_phone_when_no_parent_phone(self):
        lonely_student_user = User.objects.create_user(
            email='wa_lonely_student@test.tz', password='x', role='student', phone='+255700333444',
        )
        lonely_student = StudentProfile.objects.create(
            user=lonely_student_user, student_id='WA002', classroom=self.classroom,
        )
        ExamScore.objects.create(exam=self.exam, student=lonely_student, score=60)

        self.client.force_authenticate(self.teacher_b)
        resp = self.client.post('/api/notifications/send-whatsapp-result/', {
            'student_id': lonely_student.id, 'exam_id': self.exam.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['sent'])
        log = NotificationLog.objects.filter(recipient__email='wa_lonely_student@test.tz').first()
        self.assertIsNotNone(log)

    def test_no_score_recorded_returns_error(self):
        no_score_student_user = User.objects.create_user(email='wa_noscore@test.tz', password='x', role='student')
        no_score_student = StudentProfile.objects.create(
            user=no_score_student_user, student_id='WA003', classroom=self.classroom,
        )
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.post('/api/notifications/send-whatsapp-result/', {
            'student_id': no_score_student.id, 'exam_id': self.exam.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
