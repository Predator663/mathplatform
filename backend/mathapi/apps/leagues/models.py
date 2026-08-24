from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class LeagueSeason(models.Model):
    """
    One run of the skill-tier league system for a classroom: students are
    placed into LeagueGroup bands using their score on `baseline_exam` (the
    "first individual exam" the teacher chooses to seed placement), then
    every later exam sat by that classroom can be checked for
    promotion-worthy performance via services.evaluate_promotions().

    Deliberately scoped to one Classroom at a time — bands are only ever
    meaningful for students who actually sit the same papers. A classroom
    can have several seasons over time (one per term, one per topic block,
    etc.) — old ones are simply archived rather than deleted, since
    PromotionEvent history and Hall of Fame both read across all seasons.
    """
    class IntervalMode(models.TextChoices):
        AUTO = 'auto', 'Automatic (evenly spaced)'
        MANUAL = 'manual', 'Manual (custom bands)'

    class PromotionMode(models.TextChoices):
        AUTO = 'auto', 'Auto-apply promotions'
        MANUAL = 'manual', 'Stage for teacher approval'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        ARCHIVED = 'archived', 'Archived'

    title = models.CharField(max_length=200)
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='league_seasons')
    baseline_exam = models.ForeignKey(
        'exams.Exam', on_delete=models.CASCADE, related_name='league_seasons_baseline',
        help_text='The first individual exam used to place students into their starting band.',
    )
    interval_mode = models.CharField(max_length=10, choices=IntervalMode.choices, default=IntervalMode.AUTO)
    band_width = models.PositiveIntegerField(
        default=10, help_text='Auto mode only: width in percentage points of each band, e.g. 10 -> 0-9, 10-19 ... 90-100.',
    )
    promotion_mode = models.CharField(max_length=10, choices=PromotionMode.choices, default=PromotionMode.MANUAL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_league_seasons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'league_seasons'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.classroom}'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def top_group_order(self):
        agg = self.groups.aggregate(top=models.Max('order'))
        return agg['top']


class LeagueGroup(models.Model):
    """
    One skill band within a season, e.g. "90-100 — Elite Circle". min_mark/
    max_mark are inclusive percentage bounds used both to place students at
    season creation and to test promotion eligibility later. `order` is
    the tier rank — 0 is the lowest band, higher numbers are stronger bands
    — kept separate from the numeric interval so re-ordering never has to
    touch the marks themselves.
    """
    season = models.ForeignKey(LeagueSeason, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=100)
    min_mark = models.DecimalField(max_digits=5, decimal_places=2)
    max_mark = models.DecimalField(max_digits=5, decimal_places=2)
    order = models.PositiveIntegerField(default=0, help_text='0 = lowest tier, ascending = higher tier')
    color = models.CharField(max_length=7, default='#6366f1')
    icon = models.CharField(max_length=50, default='shield', help_text='lucide-react icon name')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'league_groups'
        ordering = ['season', 'order']
        constraints = [
            models.UniqueConstraint(fields=['season', 'order'], name='unique_league_group_order'),
        ]

    def __str__(self):
        return f'{self.name} ({self.min_mark}-{self.max_mark}%)'

    def contains(self, score) -> bool:
        return float(self.min_mark) <= float(score) <= float(self.max_mark)


class LeagueMembership(models.Model):
    """
    One student's current standing within a season. `group` always holds
    the student's CURRENT band — moved live the instant a promotion is
    applied, never lagging behind — while PromotionEvent rows keep the
    full history. `is_promotion_pending` (plus `pending_target_group`) is
    what a report/analytics page reads to render the "staged for
    promotion" badge.
    """
    season = models.ForeignKey(LeagueSeason, on_delete=models.CASCADE, related_name='memberships')
    student = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, related_name='league_memberships')
    group = models.ForeignKey(LeagueGroup, on_delete=models.CASCADE, related_name='members')
    placement_score = models.FloatField(help_text="Score %% on the season's baseline exam that placed this student.")
    latest_score = models.FloatField(null=True, blank=True, help_text='Most recently evaluated score %%.')
    latest_exam = models.ForeignKey('exams.Exam', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_promotion_pending = models.BooleanField(default=False)
    pending_target_group = models.ForeignKey(
        LeagueGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='pending_promotions',
    )
    pending_trigger_score = models.FloatField(null=True, blank=True)
    pending_trigger_exam = models.ForeignKey('exams.Exam', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'league_memberships'
        unique_together = ['season', 'student']
        ordering = ['group__order', '-latest_score']

    def __str__(self):
        return f'{self.student.full_name} — {self.group.name}'

    @property
    def is_top_tier(self):
        return self.group.order == self.season.top_group_order


class PromotionEvent(models.Model):
    """
    Audit trail of every promotion decision — the source of the "staged
    for promotion" / "promoted" badge shown on a student's report, and the
    raw data behind Hall of Fame's "most promoted" stats. Never deleted
    once decided, so a season's promotion history stays intact even after
    a membership moves again later.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Staged for Promotion'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        AUTO_APPLIED = 'auto_applied', 'Auto-Applied'

    membership = models.ForeignKey(LeagueMembership, on_delete=models.CASCADE, related_name='promotion_events')
    season = models.ForeignKey(LeagueSeason, on_delete=models.CASCADE, related_name='promotion_events')
    student = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, related_name='league_promotions')
    from_group = models.ForeignKey(LeagueGroup, on_delete=models.CASCADE, related_name='promotions_from')
    to_group = models.ForeignKey(LeagueGroup, on_delete=models.CASCADE, related_name='promotions_to')
    trigger_exam = models.ForeignKey('exams.Exam', on_delete=models.CASCADE, related_name='+')
    trigger_score = models.FloatField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='decided_promotions')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'league_promotion_events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.student.full_name}: {self.from_group.name} -> {self.to_group.name} ({self.status})'
