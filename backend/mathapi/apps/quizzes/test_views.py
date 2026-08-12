"""
Tests for the quiz analytics, CSV export, and PDF export API views.
Run with: python manage.py test mathapi.apps.quizzes.test_views -v 2
"""
import csv
import io
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import MathTopic
from .models import DailyQuiz, DailyQuizScore

User = get_user_model()


class QuizViewTestBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='View Quiz Maths', code='VWQZ')
        cls.topic = MathTopic.objects.create(subject=cls.subject, name='Trigonometry')
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='2E', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.other_classroom = Classroom.objects.create(name='2F', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.admin = User.objects.create_user(email='vq_admin@test.tz', password='x', role='super_admin')
        cls.teacher_a = User.objects.create_user(email='vq_teacher_a@test.tz', password='x', role='teacher')
        cls.teacher_b = User.objects.create_user(email='vq_teacher_b@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_a, subject=cls.subject, classroom=cls.classroom)

        cls.student = StudentProfile.objects.create(
            user=User.objects.create_user(email='vq_student@test.tz', password='x', role='student'),
            student_id='VQ001', classroom=cls.classroom,
        )

        cls.quiz = DailyQuiz.objects.create(
            date=datetime.date(2026, 4, 1), classroom=cls.classroom, subject=cls.subject,
            topic=cls.topic, term='term_1', academic_year='2026',
            max_score=10, passing_score=5, created_by=cls.teacher_a,
        )
        DailyQuizScore.objects.create(quiz=cls.quiz, student=cls.student, score=8, entered_by=cls.teacher_a)


class ClassroomAnalyticsViewTests(QuizViewTestBase):
    def test_assigned_teacher_can_view_analytics(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/quizzes/classroom/{self.classroom.id}/analytics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['overview']['quiz_count'], 1)

    def test_unassigned_teacher_is_blocked(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/quizzes/classroom/{self.classroom.id}/analytics/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_view_analytics(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(f'/api/quizzes/classroom/{self.classroom.id}/analytics/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_student_cannot_view_classroom_analytics(self):
        self.client.force_authenticate(self.student.user)
        resp = self.client.get(f'/api/quizzes/classroom/{self.classroom.id}/analytics/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_topic_filter_applied(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/quizzes/classroom/{self.classroom.id}/analytics/', {'topic_id': self.topic.id})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['overview']['quiz_count'], 1)

        other_topic = MathTopic.objects.create(subject=self.subject, name='Calculus')
        resp2 = self.client.get(f'/api/quizzes/classroom/{self.classroom.id}/analytics/', {'topic_id': other_topic.id})
        self.assertEqual(resp2.data['overview']['quiz_count'], 0)


class StudentProgressViewTests(QuizViewTestBase):
    def test_assigned_teacher_can_view_student_progress(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/quizzes/students/{self.student.id}/progress/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('streak', resp.data)
        self.assertIn('badges', resp.data)
        self.assertIn('topic_data', resp.data)

    def test_unassigned_teacher_cannot_view_student_progress(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/quizzes/students/{self.student.id}/progress/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_can_view_own_progress_via_my_progress(self):
        self.client.force_authenticate(self.student.user)
        resp = self.client.get('/api/quizzes/my-progress/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['summary']['quizzes_taken'], 1)


class QuizExportTests(QuizViewTestBase):
    def test_csv_export_contains_quiz_row(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get('/api/quizzes/quizzes/export-csv/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        rows = list(csv.reader(io.StringIO(resp.content.decode('utf-8'))))
        self.assertEqual(len(rows), 2)  # header + 1 quiz
        self.assertIn('Trigonometry', rows[1])

    def test_pdf_export_returns_pdf_for_authorized_teacher(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/quizzes/students/{self.student.id}/progress-report.pdf/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_pdf_export_blocked_for_unassigned_teacher(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/quizzes/students/{self.student.id}/progress-report.pdf/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_pdf_export_works_with_no_badges_or_quizzes(self):
        empty_student = StudentProfile.objects.create(
            user=User.objects.create_user(email='vq_empty@test.tz', password='x', role='student'),
            student_id='VQ002', classroom=self.classroom,
        )
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/quizzes/students/{empty_student.id}/progress-report.pdf/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.content.startswith(b'%PDF'))


class MyProgressStudentIdTests(QuizViewTestBase):
    def test_my_progress_includes_student_id_for_pdf_download_link(self):
        self.client.force_authenticate(self.student.user)
        resp = self.client.get('/api/quizzes/my-progress/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['student_id'], self.student.id)
