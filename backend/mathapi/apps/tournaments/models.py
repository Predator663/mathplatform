from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Tournament(models.Model):
    """
    An exam-linked competitive event. Students (or whole streams) register
    to face off before the underlying exam is sat; once the exam is scored
    and the tournament is finalized, entries are ranked by that exam's
    percentage score and challenges are resolved head-to-head.

    Deliberately tied to exactly one Exam and one Classroom — this keeps
    "the countdown" unambiguous (registration_deadline, then exam_date)
    and keeps scoring a pure read of ExamScore, never a second source of
    truth for marks.
    """
    class Mode(models.TextChoices):
        INDIVIDUAL = 'individual', 'Student vs Student'
        STREAM = 'stream', 'Stream vs Stream'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        REGISTRATION_OPEN = 'registration_open', 'Registration Open'
        REGISTRATION_CLOSED = 'registration_closed', 'Registration Closed'
        LIVE = 'live', 'Live — Awaiting Exam Results'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    title = models.CharField(max_length=200)
    codename = models.CharField(max_length=60, blank=True,
                                 help_text='Optional operation codename shown on the dossier header, e.g. "OPERATION HISABATI"')
    description = models.TextField(blank=True)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.INDIVIDUAL)
    exam = models.ForeignKey('exams.Exam', on_delete=models.CASCADE, related_name='tournaments',
                              help_text='The exam whose scores decide this tournament.')
    classroom = models.ForeignKey('students.Classroom', on_delete=models.CASCADE, related_name='tournaments')
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_deadline = models.DateTimeField(
        help_text='Countdown target while registration is open — students must register before this.')
    max_entrants = models.PositiveIntegerField(null=True, blank=True)
    is_public = models.BooleanField(default=True, help_text='Students may self-register when true')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tournaments')
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tournaments'
        ordering = ['-registration_deadline']

    def __str__(self):
        return self.title

    @property
    def is_registration_open(self):
        return self.status == self.Status.REGISTRATION_OPEN

    @property
    def is_finalized(self):
        return self.status == self.Status.COMPLETED


class TournamentEntry(models.Model):
    """
    One registered combatant — either a single student (Mode.INDIVIDUAL) or
    an entire stream (Mode.STREAM), never both. seed_average is the
    entrant's prior average % (captured at registration time) used purely
    for underdog/giant-slayer detection later — it never affects the
    actual ranking, which always comes from the live exam score.
    """
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='entries')
    student = models.ForeignKey('students.StudentProfile', on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='tournament_entries')
    stream = models.ForeignKey('students.Stream', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='tournament_entries')
    registered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                       related_name='registered_tournament_entries')
    seed_average = models.FloatField(null=True, blank=True,
                                      help_text="Entrant's prior average % at registration time")
    withdrawn = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tournament_entries'
        constraints = [
            models.UniqueConstraint(fields=['tournament', 'student'],
                                     condition=models.Q(student__isnull=False),
                                     name='unique_tournament_student_entry'),
            models.UniqueConstraint(fields=['tournament', 'stream'],
                                     condition=models.Q(stream__isnull=False),
                                     name='unique_tournament_stream_entry'),
        ]
        ordering = ['-seed_average']

    def __str__(self):
        return f'{self.display_name} — {self.tournament.title}'

    @property
    def display_name(self):
        if self.student_id:
            return self.student.full_name
        if self.stream_id:
            return str(self.stream)
        return 'Unknown Entrant'

    @property
    def entrant_type(self):
        return 'student' if self.student_id else 'stream'


class Challenge(models.Model):
    """
    A declared duel between two (or more) entries within a tournament —
    "student comes to register a challenge against another student".
    Resolution reads ExamScore once the tournament is finalized; the
    highest scorer among the challenge's entries wins.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting Results'
        RESOLVED = 'resolved', 'Resolved'
        VOID = 'void', 'Void'

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='challenges')
    label = models.CharField(max_length=120, blank=True, help_text='e.g. "Duel — Front Row Showdown"')
    entries = models.ManyToManyField(TournamentEntry, related_name='challenges')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    winner = models.ForeignKey(TournamentEntry, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='won_challenges')
    is_tie = models.BooleanField(default=False)
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='initiated_challenges')
    compatibility_note = models.TextField(
        blank=True,
        help_text=(
            "Set when this challenge's combatants weren't a close skill-level match at "
            "creation/edit time — an AI-written explanation of the mismatch (falls back to "
            "a plain algorithmic sentence if Claude is unavailable), shown to the teacher as "
            "a heads-up. Cleared automatically if a later edit brings the combatants back "
            "within the compatibility gap. See services.sync_compatibility_note()."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'tournament_challenges'
        ordering = ['-created_at']

    def __str__(self):
        return self.label or f'Challenge #{self.pk}'


class EntryResult(models.Model):
    """
    Frozen scoring dossier for one entry, (re)computed each time the
    tournament is finalized. Kept as its own row (rather than derived
    on-the-fly every request) so the leaderboard/analytics stay stable and
    fast, and so a later score correction only changes things once the
    tournament is explicitly re-finalized.
    """
    entry = models.OneToOneField(TournamentEntry, on_delete=models.CASCADE, related_name='result')
    score_percentage = models.FloatField(null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    prior_average = models.FloatField(null=True, blank=True,
                                       help_text="Entrant's historical average % before this exam")
    delta = models.FloatField(null=True, blank=True, help_text='score_percentage minus prior_average')
    is_rising_star = models.BooleanField(default=False, help_text='Improved sharply vs their own prior average')
    is_champion = models.BooleanField(default=False, help_text='Ranked #1 overall in this tournament')
    is_absent = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tournament_entry_results'
        ordering = ['rank']

    def __str__(self):
        return f'{self.entry.display_name}: rank {self.rank}'
