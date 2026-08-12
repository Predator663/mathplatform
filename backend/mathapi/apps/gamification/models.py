from django.db import models


class Badge(models.Model):
    """A system-defined achievement. Rows are seeded once from
    catalog.BADGE_CATALOG (see the 0001 migration) — not user-editable,
    so `code`/`criteria_type`/`threshold` always match what services.py
    actually checks for."""
    code          = models.SlugField(max_length=50, unique=True)
    name          = models.CharField(max_length=100)
    description   = models.CharField(max_length=255, blank=True)
    icon          = models.CharField(max_length=50, default='award', help_text='lucide-react icon name')
    criteria_type = models.CharField(max_length=30)
    threshold     = models.PositiveIntegerField(default=0)
    is_active     = models.BooleanField(default=True)

    class Meta:
        db_table = 'gamification_badges'
        ordering = ['threshold', 'name']

    def __str__(self):
        return self.name


class StudentBadge(models.Model):
    """One badge earned by one student — awarded automatically by
    services.evaluate_badges, never manually. unique_together makes
    re-evaluation idempotent (a badge is only ever awarded once)."""
    student    = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, related_name='badges')
    badge      = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='awards')
    exam       = models.ForeignKey('exams.Exam', on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text='The exam whose score triggered this award, if any.')
    quiz       = models.ForeignKey('quizzes.DailyQuiz', on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text='The daily quiz whose score triggered this award, if any.')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gamification_student_badges'
        unique_together = ['student', 'badge']
        ordering = ['-awarded_at']

    def __str__(self):
        return f'{self.student.full_name} — {self.badge.name}'


class StudentStreak(models.Model):
    """Live pass-streak state for one student, recomputed from scratch by
    services.recalculate_streak whenever a published exam's score for
    them is entered, edited, or deleted."""
    student            = models.OneToOneField('students.StudentProfile', on_delete=models.CASCADE, related_name='streak')
    current_streak     = models.PositiveIntegerField(default=0)
    longest_streak      = models.PositiveIntegerField(default=0)
    last_exam           = models.ForeignKey('exams.Exam', on_delete=models.SET_NULL, null=True, blank=True)
    last_exam_date       = models.DateField(null=True, blank=True)
    last_result_passed  = models.BooleanField(null=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gamification_student_streaks'

    def __str__(self):
        return f'{self.student.full_name}: {self.current_streak} (best {self.longest_streak})'


class QuizStreak(models.Model):
    """Daily-quiz participation streak — distinct from StudentStreak
    (which tracks *exam pass* streaks). This counts consecutive quiz
    *occurrences* the student attended (present, not absent), walking the
    actual sequence of dates quizzes were given rather than raw calendar
    days — so weekends/holidays with no quiz scheduled never break a
    streak. Recomputed from scratch by
    gamification.services.recalculate_quiz_streak whenever a quiz score
    is entered, edited, or deleted."""
    student         = models.OneToOneField('students.StudentProfile', on_delete=models.CASCADE, related_name='quiz_streak')
    current_streak  = models.PositiveIntegerField(default=0)
    longest_streak  = models.PositiveIntegerField(default=0)
    last_quiz_date  = models.DateField(null=True, blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gamification_quiz_streaks'

    def __str__(self):
        return f'{self.student.full_name}: {self.current_streak} quiz days (best {self.longest_streak})'
