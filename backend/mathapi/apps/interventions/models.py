from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# Single source of truth for the default stage sequence, mirrored by the
# frontend's read-only preview before a program is created. A teacher can
# still supply a custom stage list when creating a program (see
# services.create_program) — this is only the sensible default.
DEFAULT_STAGE_TEMPLATE = [
    {
        'title': 'Diagnostic Review',
        'description': "Pinpoint exactly which topics and question types are dragging the student down, using her full exam history rather than just the last paper.",
    },
    {
        'title': 'Targeted Practice',
        'description': "Focused practice sheets and exercises on the weak topics the diagnostic surfaced.",
    },
    {
        'title': 'Guided Support',
        'description': "One-on-one or small-group guided sessions — after-class tutoring, peer mentoring, or seating-chart pairing with a stronger student.",
    },
    {
        'title': 'Reassessment',
        'description': "A follow-up quiz or mini-test on the same weak topics to measure real movement before the next full exam.",
    },
    {
        'title': 'Mastery Check',
        'description': "Confirm the improvement held up across the next full exam before closing out the program.",
    },
]


class InterventionProgram(models.Model):
    """
    A structured, staged improvement plan for one student flagged as a
    "slow learner" — someone whose exam history (every exam she has ever
    sat, not just the last one) shows no meaningful upward trend. Stages
    must be completed strictly in order (enforced in services.start_stage),
    each one measurable via a before/after average comparison — see
    InterventionStage.
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        DISCONTINUED = 'discontinued', 'Discontinued'

    student = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, related_name='intervention_programs')
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='intervention_programs')
    subject = models.ForeignKey('accounts.Subject', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='intervention_programs')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE)
    trigger_reason = models.CharField(
        max_length=255, blank=True,
        help_text='Why this student was flagged, e.g. "No improvement across the last 6 exams".',
    )
    baseline_average = models.FloatField(help_text="Student's historical average %% at program start.")
    latest_average = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_interventions')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intervention_programs'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.student.full_name} — Intervention ({self.get_status_display()})'

    @property
    def improvement(self):
        if self.latest_average is None:
            return None
        return round(self.latest_average - self.baseline_average, 2)

    @property
    def current_stage(self):
        return (
            self.stages.filter(status=InterventionStage.Status.ACTIVE).order_by('order').first()
            or self.stages.filter(status=InterventionStage.Status.PENDING).order_by('order').first()
        )

    @property
    def stage_count(self):
        return self.stages.count()

    @property
    def completed_stage_count(self):
        return self.stages.filter(status=InterventionStage.Status.COMPLETED).count()


class InterventionStage(models.Model):
    """
    One step in the plan. Sequentially gated: a stage can only move to
    ACTIVE once every earlier-ordered stage in the same program is
    COMPLETED (or SKIPPED) — enforced server-side in
    services.start_stage, not just hidden in the UI, so "no stage can be
    reached without completing the previous" holds even against a direct
    API call.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Locked'
        ACTIVE = 'active', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        SKIPPED = 'skipped', 'Skipped'

    program = models.ForeignKey(InterventionProgram, on_delete=models.CASCADE, related_name='stages')
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    measured_before = models.FloatField(null=True, blank=True,
                                         help_text="Student's average %% right before this stage started.")
    measured_after = models.FloatField(null=True, blank=True,
                                        help_text="Student's average %% when this stage was marked complete.")
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'intervention_stages'
        ordering = ['program', 'order']
        unique_together = ['program', 'order']

    def __str__(self):
        return f'{self.program.student.full_name} — Stage {self.order}: {self.title}'

    @property
    def improvement(self):
        if self.measured_before is None or self.measured_after is None:
            return None
        return round(self.measured_after - self.measured_before, 2)

    @property
    def is_locked(self):
        return self.status == self.Status.PENDING
