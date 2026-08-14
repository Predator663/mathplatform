"""
Tests for MathTopicViewSet: CRUD, soft-delete (and the data-loss bug that
existed before this fix — hard delete would CASCADE through TopicScore /
ExamTopicWeight), restore, reorder, and scoping.
Run with: python manage.py test mathapi.apps.exams.test_topics -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from .models import MathTopic, Exam, ExamScore, ExamTopicWeight, TopicScore

User = get_user_model()


class TopicCRUDTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Topic CRUD Maths', code='TCRD')
        cls.other_subject = Subject.objects.create(name='Topic CRUD Physics', code='TCRDP')
        cls.admin = User.objects.create_user(email='tc_admin@test.tz', password='x', role='super_admin')
        cls.teacher = User.objects.create_user(email='tc_teacher@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(
            teacher=cls.teacher, subject=cls.subject,
            classroom=Classroom.objects.create(
                name='TC1', grade_level=GradeLevel.objects.create(name='F1', short_name='F1', education_level='secondary', order=1),
                stream='general', academic_year='2026',
            ),
        )

    def test_admin_can_create_topic(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/topics/', {'subject': self.subject.id, 'name': 'Fractions'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_teacher_cannot_create_topic(self):
        self.client.force_authenticate(self.teacher)
        resp = self.client.post('/api/exams/topics/', {'subject': self.subject.id, 'name': 'Fractions'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_only_sees_topics_for_own_subjects(self):
        MathTopic.objects.create(subject=self.subject, name='Algebra')
        MathTopic.objects.create(subject=self.other_subject, name='Motion')
        self.client.force_authenticate(self.teacher)
        resp = self.client.get('/api/exams/topics/')
        names = {t['name'] for t in resp.data['results']} if 'results' in resp.data else {t['name'] for t in resp.data}
        self.assertIn('Algebra', names)
        self.assertNotIn('Motion', names)

    def test_duplicate_name_within_subject_rejected(self):
        MathTopic.objects.create(subject=self.subject, name='Geometry')
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/topics/', {'subject': self.subject.id, 'name': 'Geometry'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_name_different_subject_allowed(self):
        MathTopic.objects.create(subject=self.subject, name='Vectors')
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/topics/', {'subject': self.other_subject.id, 'name': 'Vectors'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


class TopicSoftDeleteTests(APITestCase):
    """The core bug fix: destroy() must never hard-delete, since MathTopic
    is CASCADE-referenced by TopicScore and ExamTopicWeight."""

    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Soft Delete Maths', code='SDTM')
        cls.admin = User.objects.create_user(email='sd_admin@test.tz', password='x', role='super_admin')
        cls.topic = MathTopic.objects.create(subject=cls.subject, name='Trigonometry')

        cls.grade = GradeLevel.objects.create(name='F2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='SD1', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.student = StudentProfile.objects.create(
            user=User.objects.create_user(email='sd_student@test.tz', password='x', role='student'),
            student_id='SD001', classroom=cls.classroom,
        )
        cls.exam = Exam.objects.create(
            title='SD Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 1, 1), max_score=100, passing_score=30,
            subject=cls.subject, is_published=True,
        )
        cls.exam.classrooms.add(cls.classroom)
        cls.weight = ExamTopicWeight.objects.create(exam=cls.exam, topic=cls.topic, max_marks=50, weight_percentage=50)
        cls.exam_score = ExamScore.objects.create(exam=cls.exam, student=cls.student, score=70)
        cls.topic_score = TopicScore.objects.create(exam_score=cls.exam_score, topic=cls.topic, score=35, max_marks=50)

    def test_delete_does_not_hard_delete_the_row(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        # The row must still exist, just flagged inactive.
        topic = MathTopic.objects.get(id=self.topic.id)
        self.assertFalse(topic.is_active)

    def test_delete_preserves_historical_topic_scores(self):
        """This is the actual data-loss bug: before the fix, this delete
        would CASCADE and silently wipe TopicScore/ExamTopicWeight rows."""
        self.client.force_authenticate(self.admin)
        self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        self.assertTrue(TopicScore.objects.filter(id=self.topic_score.id).exists())
        self.assertTrue(ExamTopicWeight.objects.filter(id=self.weight.id).exists())

    def test_deleted_topic_excluded_from_default_list(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        resp = self.client.get('/api/exams/topics/')
        names = {t['name'] for t in resp.data['results']} if 'results' in resp.data else {t['name'] for t in resp.data}
        self.assertNotIn('Trigonometry', names)

    def test_deleted_topic_visible_with_include_inactive(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        resp = self.client.get('/api/exams/topics/', {'include_inactive': 'true'})
        names = {t['name'] for t in resp.data['results']} if 'results' in resp.data else {t['name'] for t in resp.data}
        self.assertIn('Trigonometry', names)

    def test_restore_reactivates_topic(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        resp = self.client.post(f'/api/exams/topics/{self.topic.id}/restore/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.topic.refresh_from_db()
        self.assertTrue(self.topic.is_active)

    def test_recreating_same_name_after_soft_delete_suggests_restore(self):
        self.client.force_authenticate(self.admin)
        self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        resp = self.client.post('/api/exams/topics/', {'subject': self.subject.id, 'name': 'Trigonometry'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Restore', str(resp.data))

    def test_teacher_cannot_delete_or_restore_topic(self):
        teacher = User.objects.create_user(email='sd_teacher@test.tz', password='x', role='teacher')
        self.client.force_authenticate(teacher)
        resp = self.client.delete(f'/api/exams/topics/{self.topic.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        resp2 = self.client.post(f'/api/exams/topics/{self.topic.id}/restore/')
        self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)


class TopicReorderTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Reorder Maths', code='RORD')
        cls.admin = User.objects.create_user(email='ro_admin@test.tz', password='x', role='super_admin')
        cls.t1 = MathTopic.objects.create(subject=cls.subject, name='Topic A', order=0)
        cls.t2 = MathTopic.objects.create(subject=cls.subject, name='Topic B', order=1)
        cls.t3 = MathTopic.objects.create(subject=cls.subject, name='Topic C', order=2)

    def test_reorder_persists_new_order(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/topics/reorder/', {
            'order': [
                {'id': self.t3.id, 'order': 0},
                {'id': self.t1.id, 'order': 1},
                {'id': self.t2.id, 'order': 2},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.t1.refresh_from_db(); self.t2.refresh_from_db(); self.t3.refresh_from_db()
        self.assertEqual(self.t3.order, 0)
        self.assertEqual(self.t1.order, 1)
        self.assertEqual(self.t2.order, 2)

    def test_reorder_rejects_unknown_id(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/topics/reorder/', {
            'order': [{'id': 999999, 'order': 0}],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reorder_rejects_empty_list(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/exams/topics/reorder/', {'order': []}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
