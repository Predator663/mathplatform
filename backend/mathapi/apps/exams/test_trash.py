"""
API-level verification for the exam trash feature: listing soft-deleted
exams, restoring one, and permanently emptying the trash in bulk. Run with:
    python manage.py test mathapi.apps.exams.test_trash -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, AuditLog
from mathapi.apps.students.models import GradeLevel, Classroom
from mathapi.apps.exams.models import Exam, ExamScore

User = get_user_model()


class ExamTrashTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(email='admin@trash.tz', password='x', role='super_admin')
        cls.teacher = User.objects.create_user(email='teacher@trash.tz', password='x', role='teacher')
        cls.subject = Subject.objects.create(name='Trash Maths', code='TRSH')
        cls.grade = GradeLevel.objects.create(name='Form 3', short_name='F3', education_level='secondary', order=3)
        cls.classroom = Classroom.objects.create(name='3A', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.live_exam = Exam.objects.create(
            title='Live Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 4, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.admin, is_published=True,
        )
        cls.deleted_exam_1 = Exam.objects.create(
            title='Deleted Exam One', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 3, 1), max_score=100, passing_score=30,
            subject=cls.subject, created_by=cls.teacher, is_published=True, is_deleted=True,
        )
        cls.deleted_exam_2 = Exam.objects.create(
            title='Deleted Exam Two', exam_type='mid_term', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 2, 1), max_score=50, passing_score=15,
            subject=cls.subject, created_by=cls.admin, is_published=False, is_deleted=True,
        )
        # A score hanging off a deleted exam — proves permanent delete
        # actually cascades rather than leaving orphans / erroring out.
        u = User.objects.create_user(email='stu@trash.tz', password='x', role='student')
        from mathapi.apps.students.models import StudentProfile
        cls.student = StudentProfile.objects.create(user=u, student_id='T001', classroom=cls.classroom)
        ExamScore.objects.create(exam=cls.deleted_exam_1, student=cls.student, score=40, entered_by=cls.admin)

    # ── Listing ──────────────────────────────────────────────────────────
    def test_admin_sees_all_deleted_exams_in_trash(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/trash/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)
        titles = {e['title'] for e in resp.data['results']}
        self.assertEqual(titles, {'Deleted Exam One', 'Deleted Exam Two'})
        self.assertNotIn('Live Exam', titles)

    def test_teacher_cannot_view_trash(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/exams/exams/trash/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_view_trash(self):
        resp = self.client.get('/api/exams/exams/trash/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deleted_exam_absent_from_normal_listing(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/exams/exams/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {e['id'] for e in resp.data['results']} if 'results' in resp.data else {e['id'] for e in resp.data}
        self.assertNotIn(self.deleted_exam_1.id, ids)
        self.assertIn(self.live_exam.id, ids)

    # ── Restore ──────────────────────────────────────────────────────────
    def test_admin_can_restore_deleted_exam(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(f'/api/exams/exams/{self.deleted_exam_1.id}/restore/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.deleted_exam_1.refresh_from_db()
        self.assertFalse(self.deleted_exam_1.is_deleted)
        self.assertTrue(
            AuditLog.objects.filter(model_name='Exam', description__icontains='Restored').exists()
        )

    def test_teacher_cannot_restore(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.post(f'/api/exams/exams/{self.deleted_exam_1.id}/restore/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.deleted_exam_1.refresh_from_db()
        self.assertTrue(self.deleted_exam_1.is_deleted)

    def test_restore_nonexistent_deleted_exam_404s(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(f'/api/exams/exams/{self.live_exam.id}/restore/')
        # live_exam is not soft-deleted, so restore() must not find it.
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Permanent bulk delete ────────────────────────────────────────────
    def test_empty_trash_requires_confirm(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/exams/trash/empty/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Exam.objects.filter(is_deleted=True).count(), 2)

    def test_admin_can_empty_trash(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/exams/trash/empty/', {'confirm': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['deleted_count'], 2)
        self.assertEqual(Exam.objects.filter(is_deleted=True).count(), 0)
        # Live exam untouched.
        self.assertTrue(Exam.objects.filter(id=self.live_exam.id).exists())
        # Cascade check: the score on deleted_exam_1 is gone too, not orphaned.
        self.assertFalse(ExamScore.objects.filter(exam_id=self.deleted_exam_1.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(model_name='Exam', object_id='bulk').exists()
        )

    def test_empty_trash_when_already_empty(self):
        self.client.force_authenticate(self.admin)
        self.client.post('/api/exams/exams/trash/empty/', {'confirm': True}, format='json')
        resp = self.client.post('/api/exams/exams/trash/empty/', {'confirm': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['deleted_count'], 0)

    def test_teacher_cannot_empty_trash(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.post('/api/exams/exams/trash/empty/', {'confirm': True}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Exam.objects.filter(is_deleted=True).count(), 2)
