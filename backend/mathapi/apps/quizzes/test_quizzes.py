"""
Core DailyQuiz/DailyQuizScore tests: creation, teacher/admin scoping
isolation, and bulk score entry validation.
Run with: python manage.py test mathapi.apps.quizzes.test_quizzes -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import MathTopic
from .models import DailyQuiz, DailyQuizScore

User = get_user_model()


class QuizTestBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Quiz Maths', code='QZM')
        cls.other_subject = Subject.objects.create(name='Quiz Physics', code='QZP')
        cls.topic = MathTopic.objects.create(subject=cls.subject, name='Fractions')
        cls.other_subject_topic = MathTopic.objects.create(subject=cls.other_subject, name='Motion')

        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='2A', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.other_classroom = Classroom.objects.create(name='2B', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.admin = User.objects.create_user(email='quiz_admin@test.tz', password='x', role='super_admin')
        cls.teacher_a = User.objects.create_user(email='quiz_teacher_a@test.tz', password='x', role='teacher')
        cls.teacher_b = User.objects.create_user(email='quiz_teacher_b@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_a, subject=cls.subject, classroom=cls.classroom)
        TeacherAssignment.objects.create(teacher=cls.teacher_b, subject=cls.subject, classroom=cls.other_classroom)

        cls.students = []
        for i in range(4):
            u = User.objects.create_user(email=f'quiz_student{i}@test.tz', password='x', role='student')
            cls.students.append(StudentProfile.objects.create(user=u, student_id=f'QZ{i:03d}', classroom=cls.classroom))

    def make_quiz(self, teacher, classroom=None, subject=None, topic=None, date=None, **extra):
        payload = {
            'date': (date or datetime.date(2026, 3, 3)).isoformat(),
            'classroom': (classroom or self.classroom).id,
            'subject': (subject or self.subject).id,
            'topic': topic.id if topic else self.topic.id,
            'term': 'term_1', 'academic_year': '2026',
            'max_score': 10, 'passing_score': 5,
            **extra,
        }
        self.client.force_authenticate(teacher)
        return self.client.post('/api/quizzes/quizzes/', payload, format='json')


class QuizCreateAndScopingTests(QuizTestBase):
    def test_teacher_can_create_quiz_for_own_classroom(self):
        resp = self.make_quiz(self.teacher_a)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_teacher_cannot_create_quiz_for_unassigned_classroom(self):
        resp = self.make_quiz(self.teacher_a, classroom=self.other_classroom)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_topic_must_belong_to_selected_subject(self):
        resp = self.make_quiz(self.teacher_a, topic=self.other_subject_topic)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_passing_score_cannot_exceed_max_score(self):
        resp = self.make_quiz(self.teacher_a, max_score=10, passing_score=15)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_only_sees_own_created_quizzes(self):
        self.make_quiz(self.teacher_a)
        self.make_quiz(self.teacher_b, classroom=self.other_classroom)

        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get('/api/quizzes/quizzes/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_admin_sees_all_quizzes(self):
        self.make_quiz(self.teacher_a)
        self.make_quiz(self.teacher_b, classroom=self.other_classroom)

        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/quizzes/quizzes/')
        self.assertEqual(resp.data['count'], 2)

    def test_student_sees_only_their_classroom_quizzes(self):
        self.make_quiz(self.teacher_a)  # classroom 2A
        self.make_quiz(self.teacher_b, classroom=self.other_classroom)  # 2B

        self.client.force_authenticate(self.students[0].user)  # in 2A
        resp = self.client.get('/api/quizzes/quizzes/')
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['classroom'], self.classroom.id)

    def test_teacher_cannot_delete_another_teachers_quiz(self):
        resp = self.make_quiz(self.teacher_a)
        quiz_id = resp.data['id']
        self.client.force_authenticate(self.teacher_b)
        resp2 = self.client.delete(f'/api/quizzes/quizzes/{quiz_id}/')
        # teacher_b can't even see it (scope_quizzes excludes it) -> 404, not 403
        self.assertIn(resp2.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_deleted_quiz_excluded_from_list(self):
        resp = self.make_quiz(self.teacher_a)
        quiz_id = resp.data['id']
        self.client.force_authenticate(self.teacher_a)
        del_resp = self.client.delete(f'/api/quizzes/quizzes/{quiz_id}/')
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        list_resp = self.client.get('/api/quizzes/quizzes/')
        self.assertEqual(list_resp.data['count'], 0)
        self.assertFalse(DailyQuiz.objects.get(id=quiz_id).is_deleted is False)  # confirm soft-deleted, not hard-deleted


class BulkScoreEntryTests(QuizTestBase):
    def setUp(self):
        resp = self.make_quiz(self.teacher_a)
        self.quiz_id = resp.data['id']

    def _bulk(self, teacher, scores):
        self.client.force_authenticate(teacher)
        return self.client.post(f'/api/quizzes/quizzes/{self.quiz_id}/bulk_scores/', {'scores': scores}, format='json')

    def test_valid_scores_saved(self):
        resp = self._bulk(self.teacher_a, [
            {'student_id': self.students[0].student_id, 'score': 8},
            {'student_id': self.students[1].student_id, 'score': 3},
        ])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['created'], 2)
        self.assertEqual(DailyQuizScore.objects.filter(quiz_id=self.quiz_id).count(), 2)

    def test_score_above_max_rejected(self):
        resp = self._bulk(self.teacher_a, [{'student_id': self.students[0].student_id, 'score': 99}])
        self.assertEqual(resp.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(len(resp.data['errors']), 1)
        self.assertEqual(DailyQuizScore.objects.filter(quiz_id=self.quiz_id).count(), 0)

    def test_negative_score_rejected(self):
        resp = self._bulk(self.teacher_a, [{'student_id': self.students[0].student_id, 'score': -1}])
        self.assertEqual(resp.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(len(resp.data['errors']), 1)

    def test_student_not_in_classroom_rejected(self):
        outside_user = User.objects.create_user(email='outside@test.tz', password='x', role='student')
        outside_student = StudentProfile.objects.create(user=outside_user, student_id='OUT001', classroom=self.other_classroom)
        resp = self._bulk(self.teacher_a, [{'student_id': outside_student.student_id, 'score': 5}])
        self.assertEqual(resp.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(len(resp.data['errors']), 1)
        self.assertIn('not enrolled', resp.data['errors'][0]['error'])

    def test_resubmitting_updates_not_duplicates(self):
        self._bulk(self.teacher_a, [{'student_id': self.students[0].student_id, 'score': 5}])
        resp = self._bulk(self.teacher_a, [{'student_id': self.students[0].student_id, 'score': 7}])
        self.assertEqual(resp.data['updated'], 1)
        self.assertEqual(DailyQuizScore.objects.filter(quiz_id=self.quiz_id).count(), 1)
        score = DailyQuizScore.objects.get(quiz_id=self.quiz_id, student=self.students[0])
        self.assertEqual(float(score.score), 7.0)

    def test_absent_flag_recorded(self):
        resp = self._bulk(self.teacher_a, [{'student_id': self.students[0].student_id, 'score': 0, 'is_absent': True}])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        score = DailyQuizScore.objects.get(quiz_id=self.quiz_id, student=self.students[0])
        self.assertTrue(score.is_absent)

    def test_unassigned_teacher_cannot_enter_scores(self):
        resp = self._bulk(self.teacher_b, [{'student_id': self.students[0].student_id, 'score': 5}])
        # teacher_b can't even fetch the quiz (out of scope) -> 404
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
