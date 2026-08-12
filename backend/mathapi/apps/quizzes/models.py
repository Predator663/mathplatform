from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class DailyQuiz(models.Model):
    """
    One morning quiz given to one classroom on one date, usually focused on
    a single topic. Deliberately lighter-weight than Exam — no
    draft/pending-review workflow, since these are given daily and a
    per-quiz admin approval step would make the whole feature unusable.
    Scores are visible as soon as they're entered (there's no
    is_published gate the way Exam has one).
    """
    class Term(models.TextChoices):
        # Mirrors exams.models.Exam.Term exactly (kept as a separate
        # choices class, same as accounts.SiteSettings.Term does, so this
        # app doesn't take a hard dependency on the exams app).
        TERM_I   = 'term_1', 'Term I (Jan–Apr)'
        TERM_II  = 'term_2', 'Term II (May–Aug)'
        TERM_III = 'term_3', 'Term III (Sep–Dec)'
        ANNUAL   = 'annual', 'Annual'

    date          = models.DateField()
    classroom     = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='daily_quizzes')
    subject       = models.ForeignKey('accounts.Subject', on_delete=models.PROTECT, related_name='daily_quizzes')
    # Nullable: a quiz can be a mixed/general review with no single topic.
    # Kept as SET_NULL (not CASCADE) so deleting a topic from the curriculum
    # doesn't wipe out historical quiz records — it just becomes "untagged".
    topic         = models.ForeignKey('exams.MathTopic', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='daily_quizzes')
    title         = models.CharField(max_length=200, blank=True, help_text='Optional — defaults to "<Topic> Quiz" or the date.')
    term          = models.CharField(max_length=20, choices=Term.choices)
    academic_year = models.CharField(max_length=9)
    max_score     = models.DecimalField(max_digits=6, decimal_places=2, default=10, validators=[MinValueValidator(1)])
    passing_score = models.DecimalField(max_digits=6, decimal_places=2, default=5, validators=[MinValueValidator(0)])
    notes         = models.TextField(blank=True)
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quizzes')
    is_deleted    = models.BooleanField(default=False)  # soft delete, same pattern as Exam
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_quizzes'
        ordering = ['-date', '-created_at']
        constraints = [
            models.CheckConstraint(check=models.Q(max_score__gt=0), name='dailyquiz_max_score_positive'),
        ]

    def __str__(self):
        return f'{self.display_title} — {self.classroom} ({self.date})'

    @property
    def display_title(self):
        if self.title:
            return self.title
        if self.topic_id:
            return f'{self.topic.name} Quiz'
        return f'Daily Quiz — {self.date.strftime("%d %b %Y")}'

    @property
    def passing_percentage(self):
        if self.max_score:
            return round((float(self.passing_score) / float(self.max_score)) * 100, 1)
        return 0


class DailyQuizScore(models.Model):
    quiz       = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='scores')
    student    = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, related_name='quiz_scores')
    score      = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    is_absent  = models.BooleanField(default=False)
    remarks    = models.CharField(max_length=500, blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='entered_quiz_scores')
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_quiz_scores'
        unique_together = ['quiz', 'student']
        ordering = ['-quiz__date']
        constraints = [
            models.CheckConstraint(check=models.Q(score__gte=0), name='dailyquizscore_score_non_negative'),
        ]

    def __str__(self):
        return f'{self.student.full_name} – {self.quiz}: {self.score}'

    @property
    def percentage(self):
        if self.quiz.max_score:
            return round((float(self.score) / float(self.quiz.max_score)) * 100, 1)
        return 0

    @property
    def passed(self):
        return self.score >= self.quiz.passing_score

    @property
    def letter_grade(self):
        # Mirrors exams.models.ExamScore.letter_grade exactly — keep these
        # two in sync if the official grade bands ever change.
        pct = self.percentage
        if pct >= 75: return 'A'
        if pct >= 65: return 'B'
        if pct >= 45: return 'C'
        if pct >= 30: return 'D'
        return 'F'
