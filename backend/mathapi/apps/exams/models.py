from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()


class MathTopic(models.Model):
    """
    Tanzania mathematics topics by education level.
    Primary: Numbers, Fractions, Geometry, Measurement, Statistics
    O-Level: Algebra, Geometry, Trigonometry, Statistics, Vectors, etc.
    A-Level: Calculus, Complex Numbers, Mechanics, Probability, etc.
    """
    class Level(models.TextChoices):
        PRIMARY  = 'primary',  'Primary (Std 1–7)'
        O_LEVEL  = 'o_level',  'O-Level (Form 1–4)'
        A_LEVEL  = 'a_level',  'A-Level (Form 5–6)'
        ALL      = 'all',      'All Levels'

    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color       = models.CharField(max_length=7, default='#6366f1')
    level       = models.CharField(max_length=20, choices=Level.choices, default=Level.O_LEVEL)
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'math_topics'
        ordering = ['level', 'order', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_level_display()})'


class Exam(models.Model):
    class ExamType(models.TextChoices):
        MONTHLY_TEST = 'monthly_test', 'Monthly Test'
        MID_TERM     = 'mid_term',     'Mid-Term Exam'
        TERMINAL     = 'terminal',     'Terminal Exam (End of Term)'
        MOCK         = 'mock',         'Mock Exam (Mazoezi)'
        NECTA        = 'necta',        'NECTA (National)'
        PSLE         = 'psle',         'PSLE (Std 7)'
        CSEE         = 'csee',         'CSEE (Form 4)'
        ACSEE        = 'acsee',        'ACSEE (Form 6)'
        DIAGNOSTIC   = 'diagnostic',   'Diagnostic Test'

    class Term(models.TextChoices):
        TERM_I   = 'term_1', 'Term I (Jan–Apr)'
        TERM_II  = 'term_2', 'Term II (May–Aug)'
        TERM_III = 'term_3', 'Term III (Sep–Dec)'
        ANNUAL   = 'annual', 'Annual'

    title         = models.CharField(max_length=200)
    exam_type     = models.CharField(max_length=20, choices=ExamType.choices)
    term          = models.CharField(max_length=20, choices=Term.choices)
    academic_year = models.CharField(max_length=9)   # e.g. "2024"
    exam_date     = models.DateField()
    max_score     = models.DecimalField(max_digits=6, decimal_places=2,
                                         validators=[MinValueValidator(1)])
    passing_score = models.DecimalField(max_digits=6, decimal_places=2,
                                         validators=[MinValueValidator(0)])
    topics        = models.ManyToManyField(MathTopic, through='ExamTopicWeight', blank=True)
    classrooms    = models.ManyToManyField('students.Classroom', related_name='exams', blank=True)
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                       related_name='created_exams')
    description   = models.TextField(blank=True)
    is_published  = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exams'
        ordering = ['-exam_date']

    def __str__(self):
        return f'{self.title} ({self.academic_year})'

    @property
    def passing_percentage(self):
        if self.max_score:
            return round((float(self.passing_score) / float(self.max_score)) * 100, 1)
        return 0


class ExamTopicWeight(models.Model):
    exam             = models.ForeignKey(Exam, on_delete=models.CASCADE,
                                          related_name='topic_weights')
    topic            = models.ForeignKey(MathTopic, on_delete=models.CASCADE,
                                          related_name='exam_weights')
    max_marks        = models.DecimalField(max_digits=6, decimal_places=2,
                                            validators=[MinValueValidator(0)])
    weight_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = 'exam_topic_weights'
        unique_together = ['exam', 'topic']

    def __str__(self):
        return f'{self.exam.title} – {self.topic.name} ({self.max_marks} marks)'


class ExamScore(models.Model):
    exam       = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='scores')
    student    = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE,
                                    related_name='exam_scores')
    score      = models.DecimalField(max_digits=6, decimal_places=2,
                                      validators=[MinValueValidator(0)])
    is_absent  = models.BooleanField(default=False)
    remarks    = models.CharField(max_length=500, blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='entered_scores')
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'exam_scores'
        unique_together = ['exam', 'student']
        ordering = ['-exam__exam_date']

    def __str__(self):
        return f'{self.student.full_name} – {self.exam.title}: {self.score}'

    @property
    def percentage(self):
        if self.exam.max_score:
            return round((float(self.score) / float(self.exam.max_score)) * 100, 1)
        return 0

    @property
    def passed(self):
        return self.score >= self.exam.passing_score

    @property
    def letter_grade(self):
        """
        Grading scale:
          A  75 – 100
          B  65 –  74
          C  45 –  64
          D  30 –  44
          F   0 –  29
        """
        pct = self.percentage
        if pct >= 75: return 'A'
        if pct >= 65: return 'B'
        if pct >= 45: return 'C'
        if pct >= 30: return 'D'
        return 'F'

    @property
    def grade_points(self):
        """NECTA grade points for division calculation (O-Level)."""
        grade_map = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'F': 5}
        return grade_map.get(self.letter_grade, 5)


class TopicScore(models.Model):
    exam_score = models.ForeignKey(ExamScore, on_delete=models.CASCADE,
                                    related_name='topic_scores')
    topic      = models.ForeignKey(MathTopic, on_delete=models.CASCADE,
                                    related_name='student_scores')
    score      = models.DecimalField(max_digits=6, decimal_places=2,
                                      validators=[MinValueValidator(0)])
    max_marks  = models.DecimalField(max_digits=6, decimal_places=2,
                                      validators=[MinValueValidator(0)])

    class Meta:
        db_table = 'topic_scores'
        unique_together = ['exam_score', 'topic']

    @property
    def percentage(self):
        if self.max_marks:
            return round((float(self.score) / float(self.max_marks)) * 100, 1)
        return 0


class ScoreEditLog(models.Model):
    exam_score  = models.ForeignKey(ExamScore, on_delete=models.CASCADE,
                                     related_name='edit_logs')
    changed_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    old_score   = models.DecimalField(max_digits=6, decimal_places=2)
    new_score   = models.DecimalField(max_digits=6, decimal_places=2)
    reason      = models.CharField(max_length=500, blank=True)
    changed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'score_edit_logs'
        ordering = ['-changed_at']
