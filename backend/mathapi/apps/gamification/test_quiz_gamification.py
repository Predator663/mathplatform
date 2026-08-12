"""
Tests for gamification.services quiz-streak recalculation and quiz badges.
Run with: python manage.py test mathapi.apps.gamification.test_quiz_gamification -v 2
"""
import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model

from mathapi.apps.accounts.models import Subject
from mathapi.apps.students.models import GradeLevel, Classroom, StudentProfile
from mathapi.apps.quizzes.models import DailyQuiz, DailyQuizScore
from .models import QuizStreak, StudentBadge

User = get_user_model()


def make_quiz(subject, classroom, teacher, date, **extra):
    defaults = dict(term='term_1', academic_year='2026', max_score=10, passing_score=5)
    defaults.update(extra)
    return DailyQuiz.objects.create(
        date=date, classroom=classroom, subject=subject, created_by=teacher, **defaults,
    )


class QuizStreakTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Streak Quiz Maths', code='SKQZ')
        cls.grade = GradeLevel.objects.create(name='Form 2', short_name='F2', education_level='secondary', order=2)
        cls.classroom = Classroom.objects.create(name='2D', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='sk_teacher@test.tz', password='x', role='teacher')
        cls.student = StudentProfile.objects.create(
            user=User.objects.create_user(email='sk_student@test.tz', password='x', role='student'),
            student_id='SK001', classroom=cls.classroom,
        )

    def test_streak_increments_on_consecutive_attended_quiz_days(self):
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 5))  # Monday
        DailyQuizScore.objects.create(quiz=q1, student=self.student, score=3, entered_by=self.teacher)  # even a fail counts as "attended"
        streak = QuizStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 1)

        # Skip the weekend entirely — no quiz Sat/Sun — then Monday again.
        q2 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 12))
        DailyQuizScore.objects.create(quiz=q2, student=self.student, score=8, entered_by=self.teacher)
        streak.refresh_from_db()
        self.assertEqual(streak.current_streak, 2, 'A gap with no quiz scheduled must not break the streak')

    def test_absence_breaks_streak(self):
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 5))
        DailyQuizScore.objects.create(quiz=q1, student=self.student, score=6, entered_by=self.teacher)
        q2 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 6))
        DailyQuizScore.objects.create(quiz=q2, student=self.student, score=0, is_absent=True, entered_by=self.teacher)

        streak = QuizStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 0)
        self.assertEqual(streak.longest_streak, 1)  # high-water mark preserved

    def test_fail_still_counts_as_attended(self):
        # Unlike exam pass-streaks, quiz streaks are about participation,
        # not passing — a low score should NOT reset it.
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 5))
        DailyQuizScore.objects.create(quiz=q1, student=self.student, score=1, entered_by=self.teacher)  # well below passing
        q2 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 6))
        DailyQuizScore.objects.create(quiz=q2, student=self.student, score=2, entered_by=self.teacher)

        streak = QuizStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 2)

    def test_multiple_quizzes_same_day_count_as_one_streak_day(self):
        other_subject = Subject.objects.create(name='Streak Quiz Physics', code='SKQZP')
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 5))
        q1b = make_quiz(other_subject, self.classroom, self.teacher, datetime.date(2026, 1, 5))
        DailyQuizScore.objects.create(quiz=q1, student=self.student, score=5, entered_by=self.teacher)
        DailyQuizScore.objects.create(quiz=q1b, student=self.student, score=5, entered_by=self.teacher)

        streak = QuizStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 1)

    def test_deleted_quiz_does_not_affect_streak(self):
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 5), is_deleted=True)
        DailyQuizScore.objects.create(quiz=q1, student=self.student, score=9, entered_by=self.teacher)
        self.assertFalse(QuizStreak.objects.filter(student=self.student).exists())

    def test_deleting_score_recalculates_streak(self):
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 5))
        q2 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 6))
        DailyQuizScore.objects.create(quiz=q1, student=self.student, score=5, entered_by=self.teacher)
        s2 = DailyQuizScore.objects.create(quiz=q2, student=self.student, score=5, entered_by=self.teacher)
        streak = QuizStreak.objects.get(student=self.student)
        self.assertEqual(streak.current_streak, 2)

        s2.delete()
        streak.refresh_from_db()
        self.assertEqual(streak.current_streak, 1)


class QuizBadgeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.subject = Subject.objects.create(name='Badge Quiz Maths', code='BGQZ')
        cls.grade = GradeLevel.objects.create(name='Form 4', short_name='F4', education_level='secondary', order=4)
        cls.classroom = Classroom.objects.create(name='4A', grade_level=cls.grade, stream='general', academic_year='2026')
        cls.teacher = User.objects.create_user(email='bg_teacher@test.tz', password='x', role='teacher')
        cls.student = StudentProfile.objects.create(
            user=User.objects.create_user(email='bg_student@test.tz', password='x', role='student'),
            student_id='BG001', classroom=cls.classroom,
        )

    def test_quiz_streak_5_badge_awarded(self):
        for i in range(5):
            q = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, i + 1))
            DailyQuizScore.objects.create(quiz=q, student=self.student, score=5, entered_by=self.teacher)
        codes = set(StudentBadge.objects.filter(student=self.student).values_list('badge__code', flat=True))
        self.assertIn('quiz_streak_5', codes)
        self.assertNotIn('quiz_streak_20', codes)

    def test_quiz_perfect_badge_awarded(self):
        q = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 1), max_score=10)
        DailyQuizScore.objects.create(quiz=q, student=self.student, score=10, entered_by=self.teacher)
        codes = set(StudentBadge.objects.filter(student=self.student).values_list('badge__code', flat=True))
        self.assertIn('quiz_perfect', codes)

    def test_quiz_badges_never_awarded_twice(self):
        q1 = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 1), max_score=10)
        score = DailyQuizScore.objects.create(quiz=q1, student=self.student, score=10, entered_by=self.teacher)
        count_before = StudentBadge.objects.filter(student=self.student, badge__code='quiz_perfect').count()
        score.remarks = 'verified'
        score.save()  # re-save, should not double-award
        count_after = StudentBadge.objects.filter(student=self.student, badge__code='quiz_perfect').count()
        self.assertEqual(count_before, 1)
        self.assertEqual(count_after, 1)

    def test_exam_badges_unaffected_by_quiz_scores(self):
        # A quiz-only student should never pick up exam-badges just from quizzes.
        for i in range(5):
            q = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, i + 1))
            DailyQuizScore.objects.create(quiz=q, student=self.student, score=5, entered_by=self.teacher)
        codes = set(StudentBadge.objects.filter(student=self.student).values_list('badge__code', flat=True))
        self.assertNotIn('streak_3', codes)   # exam pass-streak badge
        self.assertNotIn('first_exam', codes)

    def test_get_student_quiz_progress_only_returns_quiz_badges(self):
        from mathapi.apps.gamification import services

        # Give the student both an exam badge and a quiz badge, then check
        # get_student_quiz_progress only surfaces the quiz one.
        from mathapi.apps.exams.models import Exam, ExamScore
        exam = Exam.objects.create(
            title='Badge Check Exam', exam_type='monthly_test', term='term_1', academic_year='2026',
            exam_date=datetime.date(2026, 1, 1), max_score=100, passing_score=30,
            subject=self.subject, is_published=True,
        )
        exam.classrooms.add(self.classroom)
        ExamScore.objects.create(exam=exam, student=self.student, score=90)  # triggers 'first_exam'

        q = make_quiz(self.subject, self.classroom, self.teacher, datetime.date(2026, 1, 1), max_score=10)
        DailyQuizScore.objects.create(quiz=q, student=self.student, score=10, entered_by=self.teacher)  # triggers 'quiz_perfect'

        progress = services.get_student_quiz_progress(self.student)
        codes = {b.badge.code for b in progress['badges']}
        self.assertIn('quiz_perfect', codes)
        self.assertNotIn('first_exam', codes)
