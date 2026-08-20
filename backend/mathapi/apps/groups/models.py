from django.db import models
from django.contrib.auth import get_user_model
from mathapi.apps.exams.models import Exam

User = get_user_model()

# A rotating palette used to give auto-generated groups a distinct colour
# before a badge image is uploaded. Kept in sync with the frontend's
# BADGE_PALETTE (frontend/src/pages/groups/GroupsPage.tsx) purely for a
# nicer default — the value stored here is the source of truth either way.
DEFAULT_BADGE_COLORS = [
    '#2563eb', '#10b981', '#f59e0b', '#8b5cf6',
    '#f43f5e', '#06b6d4', '#84cc16', '#ec4899',
]


class PerformanceTier(models.TextChoices):
    """
    Mirrors the letter-grade bands already used everywhere else in the app
    (ExamScore.letter_grade, reports/pdf_engine._letter_grade,
    reports/excel_engine._letter_grade_xl — all 75/65/45/30) so a student
    labelled "very strong" here always corresponds to an A, "strong" to a
    B, and so on. Introducing a different cutoff here would let the same
    student be an "A" on their report card and merely "average" on the
    grouping page, which would look like a bug even though it wouldn't be
    one technically.
    """
    VERY_STRONG = 'very_strong', 'Very Strong'
    STRONG      = 'strong',      'Strong'
    AVERAGE     = 'average',     'Average'
    WEAK        = 'weak',        'Weak'
    UNRATED     = 'unrated',     'Not Yet Rated'


class StudentGroup(models.Model):
    """
    A peer-learning group within a classroom — e.g. for pairing strong
    students with weaker ones. Groups are always scoped to one classroom
    and one academic year; a fresh set of groups is expected each year.
    """
    classroom     = models.ForeignKey('students.Classroom', on_delete=models.CASCADE,
                                       related_name='student_groups')
    name          = models.CharField(max_length=100)
    academic_year = models.CharField(max_length=9)
    subject       = models.ForeignKey('accounts.Subject', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='student_groups',
                                       help_text='Optional — restrict grouping/ranking to one subject')
    stream        = models.ForeignKey('students.Stream', on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='student_groups',
                                       help_text='Optional — restrict this group to students in one stream '
                                                  'within the classroom (e.g. Form 2 "A"). Must belong to the '
                                                  'same classroom as the group.')
    term          = models.CharField(max_length=20, choices=Exam.Term.choices, blank=True)
    description   = models.TextField(blank=True)
    badge_image   = models.ImageField(upload_to='group_badges/', null=True, blank=True)
    badge_color   = models.CharField(max_length=7, default='#2563eb',
                                      help_text='Fallback colour swatch used until a badge image is uploaded')
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                       related_name='created_groups')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'student_groups'
        unique_together = ['classroom', 'name', 'academic_year']
        ordering = ['classroom', 'name']

    def __str__(self):
        return f'{self.name} — {self.classroom}'

    @property
    def member_count(self):
        if hasattr(self, 'annotated_member_count'):
            return self.annotated_member_count
        return self.memberships.count()


class GroupMembership(models.Model):
    """One student's placement in one group, with the performance tier
    they had *at the time they were placed* — kept even if later exams
    change their live average, so exported rosters stay historically
    accurate for whichever grouping round they describe."""
    group        = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name='memberships')
    student      = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE,
                                      related_name='group_memberships')
    tier         = models.CharField(max_length=20, choices=PerformanceTier.choices,
                                     default=PerformanceTier.UNRATED)
    average_at_placement = models.FloatField(null=True, blank=True,
                                              help_text='Student\'s average % when placed, for reference')
    is_anchor    = models.BooleanField(default=False,
                                        help_text='True if this student is one of the group\'s designated strong/very-strong anchors')
    joined_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_memberships'
        # A student can only be in one group at a time *within the same
        # classroom* — enforced in the view/service layer (a DB-level
        # constraint can't easily span the classroom FK on StudentGroup),
        # but a student can never be in the same group twice.
        unique_together = ['group', 'student']
        ordering = ['-average_at_placement']

    def __str__(self):
        return f'{self.student.full_name} in {self.group.name}'


class PeerConstraint(models.Model):
    """
    A standing rule about two students in the same classroom that
    auto-generate (and, in future, manual transfer warnings) should
    respect: keep them apart, or keep them together. Persists across
    grouping rounds — a personality conflict noted this term is still
    worth respecting next term — unlike GroupMembership, which is
    per-round.
    """
    class ConstraintType(models.TextChoices):
        AVOID  = 'avoid',  'Keep Apart'
        PREFER = 'prefer', 'Keep Together'

    classroom       = models.ForeignKey('students.Classroom', on_delete=models.CASCADE,
                                         related_name='peer_constraints')
    # Always stored with student_a_id < student_b_id (enforced in save())
    # so the same pair can't be recorded twice in reverse order.
    student_a       = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE,
                                         related_name='peer_constraints_as_a')
    student_b       = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE,
                                         related_name='peer_constraints_as_b')
    constraint_type = models.CharField(max_length=10, choices=ConstraintType.choices)
    reason          = models.CharField(max_length=255, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                         related_name='created_peer_constraints')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'peer_constraints'
        unique_together = ['classroom', 'student_a', 'student_b', 'constraint_type']
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if self.student_a_id and self.student_b_id and self.student_a_id > self.student_b_id:
            self.student_a_id, self.student_b_id = self.student_b_id, self.student_a_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.get_constraint_type_display()}: {self.student_a_id} & {self.student_b_id}'


class GroupAssignment(models.Model):
    """
    A piece of group work (classwork, homework, project, practical,
    presentation...) given to some or all of a classroom's peer groups,
    to be marked once per group rather than once per student. Mirrors
    Exam's shape (classroom/subject/term/academic_year/date/max_score)
    so it slots into the same mental model teachers already have, but
    stays in the groups app since it's graded at group granularity.
    """
    class AssignmentType(models.TextChoices):
        CLASSWORK    = 'classwork',    'Classwork'
        HOMEWORK     = 'homework',     'Homework'
        PROJECT      = 'project',      'Project'
        PRACTICAL    = 'practical',    'Practical'
        PRESENTATION = 'presentation', 'Presentation'
        OTHER        = 'other',        'Other'

    classroom       = models.ForeignKey('students.Classroom', on_delete=models.CASCADE,
                                         related_name='group_assignments')
    stream          = models.ForeignKey('students.Stream', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='group_assignments',
                                         help_text='Optional — restrict this assignment to groups in one stream.')
    subject         = models.ForeignKey('accounts.Subject', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='group_assignments')
    title           = models.CharField(max_length=200)
    description     = models.TextField(blank=True)
    assignment_type = models.CharField(max_length=20, choices=AssignmentType.choices,
                                        default=AssignmentType.CLASSWORK)
    term            = models.CharField(max_length=20, choices=Exam.Term.choices, blank=True)
    academic_year   = models.CharField(max_length=9)
    date_given      = models.DateField()
    due_date        = models.DateField(null=True, blank=True)
    max_score       = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                         related_name='created_group_assignments')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'group_assignments'
        ordering = ['-date_given', '-created_at']

    def __str__(self):
        return f'{self.title} — {self.classroom} ({self.academic_year})'


class GroupAssignmentScore(models.Model):
    """
    One group's mark for one GroupAssignment. This is the source of
    truth — individual member marks (GroupAssignmentMemberMark) default
    to this score and only diverge when a teacher records a per-student
    adjustment (e.g. a student who didn't contribute).
    """
    assignment = models.ForeignKey(GroupAssignment, on_delete=models.CASCADE, related_name='group_scores')
    group      = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name='assignment_scores')
    score      = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    is_absent  = models.BooleanField(default=False, help_text='Whole group did not submit / present.')
    remarks    = models.CharField(max_length=500, blank=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='entered_group_assignment_scores')
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'group_assignment_scores'
        unique_together = ['assignment', 'group']
        ordering = ['-assignment__date_given', 'group__name']

    def __str__(self):
        return f'{self.group.name} – {self.assignment.title}: {self.score}'

    @property
    def percentage(self):
        if self.assignment.max_score:
            return round((float(self.score) / float(self.assignment.max_score)) * 100, 1)
        return 0.0


class GroupAssignmentMemberMark(models.Model):
    """
    A student's effective mark for one group assignment. Created
    automatically for every current member when a group's score is
    recorded, defaulting to the group score with no adjustment — so
    'record marks once per group' is the normal path, while still
    letting a teacher tune an individual student's mark (bonus for
    carrying the group, penalty for not contributing, or excuse them
    entirely) without ever having to hand-enter every student.
    """
    group_score = models.ForeignKey(GroupAssignmentScore, on_delete=models.CASCADE, related_name='member_marks')
    student     = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE,
                                     related_name='group_assignment_marks')
    adjustment  = models.DecimalField(max_digits=6, decimal_places=2, default=0,
                                       help_text='Added to (or, if negative, subtracted from) the group score '
                                                  'for this student only.')
    is_excused  = models.BooleanField(default=False,
                                       help_text='Excluded from this student\'s and the group\'s analytics '
                                                  '(e.g. was absent for this piece of work).')
    note        = models.CharField(max_length=255, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'group_assignment_member_marks'
        unique_together = ['group_score', 'student']
        ordering = ['student__user__first_name']

    def __str__(self):
        return f'{self.student.full_name} – {self.group_score.assignment.title}'

    @property
    def effective_score(self):
        max_score = float(self.group_score.assignment.max_score or 0)
        raw = float(self.group_score.score) + float(self.adjustment)
        return round(max(0.0, min(raw, max_score)), 2) if max_score else round(max(0.0, raw), 2)

    @property
    def percentage(self):
        max_score = float(self.group_score.assignment.max_score or 0)
        if not max_score:
            return 0.0
        return round((self.effective_score / max_score) * 100, 1)


class GroupTransferLog(models.Model):
    """Audit trail for every move of a student between groups, so
    'balanced groups' stays explainable rather than a black box."""
    student         = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE,
                                         related_name='group_transfers')
    from_group      = models.ForeignKey(StudentGroup, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='transfers_out')
    to_group        = models.ForeignKey(StudentGroup, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='transfers_in')
    reason          = models.CharField(max_length=255, blank=True)
    warnings        = models.TextField(blank=True, help_text='Balance warnings noted at transfer time, semicolon-separated')
    transferred_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='group_transfers_made')
    transferred_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_transfer_logs'
        ordering = ['-transferred_at']

    def __str__(self):
        f = self.from_group.name if self.from_group_id else '—'
        t = self.to_group.name if self.to_group_id else '—'
        return f'{self.student.full_name}: {f} → {t}'
