"""
Tests for streak recalculation, badge awarding, and the progress endpoints.
Run with: python manage.py test mathapi.apps.gamification -v 2
"""
import datetime
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject, TeacherAssignment
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.exams.models import Exam, ExamScore
from .models import StudentStreak, StudentBadge, Badge

User = get_user_model()


def make_exam(subject, classroom, title, exam_date, *, published=True, max_score=100, passing_score=30):
    exam = Exam.objects.create(
        title=title, exam_type='monthly_test', term='term_1', academic_year='2026',
        exam_date=exam_date, max_score=max_score, passing_score=passing_score,
        subject=subject, is_published=published,
    )
    exam.classrooms.add(classroom)
    return exam


class StreakAndBadgeTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Gamification Maths', code='GAMM')
        cls.grade = GradeLevel.objects.create(name='Form 3', short_name='F3', education_level='secondary', order=3)
        cls.classroom = Classroom.objects.create(name='3A', grade_level=cls.grade, stream='general', academic_year='2026')
        student_user = User.objects.create_user(email='gamified_student@test.tz', password='x', role='student')
        cls.student = StudentProfile.objects.create(user=student_user, student_id='GAM001', classroom=cls.classroom)

    def _score(self, exam, value, *, absent=False):
        return ExamScore.objects.create(exam=exam, student=self.student, score=value, is_absent=absent)

    def test_streak_increments_on_consecutive_passes(self):
        e1 = make_exam(self.subject, self.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        self._score(e1, 50)  # pass (>=30)
        streak = StudentStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 1)

        e2 = make_exam(self.subject, self.classroom, 'Exam 2', datetime.date(2026, 2, 1))
        self._score(e2, 60)
        streak.refresh_from_db()
        self.assertEqual(streak.current_streak, 2)
        self.assertEqual(streak.longest_streak, 2)

    def test_streak_resets_on_fail(self):
        e1 = make_exam(self.subject, self.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        self._score(e1, 50)
        e2 = make_exam(self.subject, self.classroom, 'Exam 2', datetime.date(2026, 2, 1))
        self._score(e2, 10)  # fail
        streak = StudentStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 0)
        self.assertEqual(streak.longest_streak, 1)  # high-water mark preserved

    def test_absence_does_not_count_and_does_not_reset(self):
        e1 = make_exam(self.subject, self.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        self._score(e1, 50)
        e2 = make_exam(self.subject, self.classroom, 'Exam 2', datetime.date(2026, 2, 1))
        self._score(e2, 0, absent=True)
        streak = StudentStreak.objects.get(student=self.student)
        # The absence is excluded entirely — streak is still 1 from exam 1.
        self.assertEqual(streak.current_streak, 1)

    def test_unpublished_exam_does_not_affect_streak(self):
        e1 = make_exam(self.subject, self.classroom, 'Draft Exam', datetime.date(2026, 1, 1), published=False)
        self._score(e1, 90)
        self.assertFalse(StudentStreak.objects.filter(student=self.student).exists())

    def test_streak_badges_awarded_at_thresholds(self):
        for i in range(3):
            e = make_exam(self.subject, self.classroom, f'Exam {i}', datetime.date(2026, 1, i + 1))
            self._score(e, 50)
        codes = set(StudentBadge.objects.filter(student=self.student).values_list('badge__code', flat=True))
        self.assertIn('first_exam', codes)
        self.assertIn('streak_3', codes)
        self.assertNotIn('streak_5', codes)

    def test_perfect_score_badge(self):
        e = make_exam(self.subject, self.classroom, 'Perfect Exam', datetime.date(2026, 1, 1), max_score=50)
        self._score(e, 50)  # 100%
        codes = set(StudentBadge.objects.filter(student=self.student).values_list('badge__code', flat=True))
        self.assertIn('perfect_score', codes)

    def test_comeback_badge(self):
        e1 = make_exam(self.subject, self.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        self._score(e1, 10)  # fail
        e2 = make_exam(self.subject, self.classroom, 'Exam 2', datetime.date(2026, 2, 1))
        self._score(e2, 50)  # pass right after a fail
        codes = set(StudentBadge.objects.filter(student=self.student).values_list('badge__code', flat=True))
        self.assertIn('comeback', codes)

    def test_badge_never_awarded_twice(self):
        e1 = make_exam(self.subject, self.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        score = self._score(e1, 50)
        count_before = StudentBadge.objects.filter(student=self.student, badge__code='first_exam').count()
        # Re-saving the same score (e.g. a remark to the same value) must not duplicate the award.
        score.remarks = 'rechecked, same score'
        score.save()
        count_after = StudentBadge.objects.filter(student=self.student, badge__code='first_exam').count()
        self.assertEqual(count_before, 1)
        self.assertEqual(count_after, 1)

    def test_deleting_a_score_recalculates_streak(self):
        e1 = make_exam(self.subject, self.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        self._score(e1, 50)
        e2 = make_exam(self.subject, self.classroom, 'Exam 2', datetime.date(2026, 2, 1))
        score2 = self._score(e2, 60)
        streak = StudentStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 2)

        score2.delete()
        streak.refresh_from_db()
        self.assertEqual(streak.current_streak, 1)


class ProgressEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Progress Maths', code='PROM')
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='2A', grade_level=cls.grade, stream='general', academic_year='2026')

        cls.student_user = User.objects.create_user(email='progress_student@test.tz', password='x', role='student')
        cls.student = StudentProfile.objects.create(user=cls.student_user, student_id='PRG001', classroom=cls.classroom)

        cls.teacher_a = User.objects.create_user(email='progress_teacher_a@test.tz', password='x', role='teacher')
        cls.teacher_b = User.objects.create_user(email='progress_teacher_b@test.tz', password='x', role='teacher')
        TeacherAssignment.objects.create(teacher=cls.teacher_b, subject=cls.subject, classroom=cls.classroom)

        e1 = make_exam(cls.subject, cls.classroom, 'Exam 1', datetime.date(2026, 1, 1))
        ExamScore.objects.create(exam=e1, student=cls.student, score=50)

    def test_student_can_view_own_progress(self):
        self.client.force_authenticate(self.student_user)
        resp = self.client.get('/api/gamification/my-progress/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['streak']['current_streak'], 1)
        self.assertTrue(len(resp.data['badges']) >= 1)

    def test_assigned_teacher_can_view_student_progress(self):
        self.client.force_authenticate(self.teacher_b)
        resp = self.client.get(f'/api/gamification/students/{self.student.id}/progress/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unassigned_teacher_cannot_view_student_progress(self):
        self.client.force_authenticate(self.teacher_a)
        resp = self.client.get(f'/api/gamification/students/{self.student.id}/progress/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_badge_catalog_is_public_to_authenticated_users(self):
        self.client.force_authenticate(self.student_user)
        resp = self.client.get('/api/gamification/badges/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 6)
