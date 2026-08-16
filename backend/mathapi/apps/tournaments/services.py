"""
All tournament scoring logic lives here, kept deliberately stateless where
possible: entrant scores are always read fresh from ExamScore, never
duplicated. EntryResult rows are a cache of that read, rebuilt from scratch
every time finalize_tournament() runs — exactly the same "safe to
re-run" philosophy as gamification.services.recalculate_streak.
"""
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from mathapi.apps.exams.models import ExamScore
from .models import Tournament, TournamentEntry, Challenge, EntryResult

GIANT_SLAYER_GAP = 12.0     # percentage points the winner must have trailed the loser's seed by
RISING_STAR_DELTA = 15.0    # percentage points above own prior average to count as a rising star


def _student_entry_score(student_id, exam):
    """Live percentage for one student on this exam, or None if unscored/absent."""
    try:
        score = ExamScore.objects.get(student_id=student_id, exam=exam, is_absent=False)
    except ExamScore.DoesNotExist:
        return None
    return score.percentage


def _stream_entry_score(stream_id, exam):
    """Average percentage across every present, scored student in this stream."""
    scores = ExamScore.objects.filter(student__stream_id=stream_id, exam=exam, is_absent=False)
    if not scores.exists():
        return None
    total = sum(s.percentage for s in scores)
    return round(total / scores.count(), 2)


def get_entry_score(entry: TournamentEntry):
    """Current live score for an entry — the single source of truth used both
    for challenge resolution and for the finalize leaderboard."""
    if entry.student_id:
        return _student_entry_score(entry.student_id, entry.tournament.exam)
    if entry.stream_id:
        return _stream_entry_score(entry.stream_id, entry.tournament.exam)
    return None


def get_prior_average(student, exclude_exam):
    """A student's historical average % across other published, non-absent
    exams — the baseline 'rising star' and 'underdog' compare against."""
    agg = (
        ExamScore.objects.filter(student=student, is_absent=False, exam__is_published=True)
        .exclude(exam=exclude_exam)
        .aggregate(avg=Avg('score'))
    )
    if agg['avg'] is None:
        return None
    # Re-derive as a percentage using each exam's own max_score, not a raw-score average
    scores = (
        ExamScore.objects.filter(student=student, is_absent=False, exam__is_published=True)
        .exclude(exam=exclude_exam)
        .select_related('exam')
    )
    if not scores.exists():
        return None
    return round(sum(s.percentage for s in scores) / scores.count(), 2)


@transaction.atomic
def register_entry(tournament: Tournament, *, student=None, stream=None, registered_by=None):
    """Registers one combatant. Captures seed_average at this moment so later
    giant-slayer/underdog checks reflect the strength picture at sign-up time,
    not a strength that only became visible after the fact."""
    seed_average = None
    if student is not None:
        seed_average = get_prior_average(student, exclude_exam=tournament.exam)
    entry = TournamentEntry.objects.create(
        tournament=tournament, student=student, stream=stream,
        registered_by=registered_by, seed_average=seed_average,
    )
    return entry


@transaction.atomic
def resolve_challenge(challenge: Challenge):
    """Reads live exam scores for every entry in the challenge and declares
    a winner. No-ops (stays pending) until every entry has a score."""
    entries = list(challenge.entries.select_related('student', 'stream').all())
    if len(entries) < 2:
        return challenge

    scored = [(e, get_entry_score(e)) for e in entries]
    if any(score is None for _, score in scored):
        return challenge  # someone hasn't sat/been scored yet — stay pending

    scored.sort(key=lambda pair: pair[1], reverse=True)
    top_score = scored[0][1]
    leaders = [e for e, s in scored if s == top_score]

    challenge.status = Challenge.Status.RESOLVED
    challenge.resolved_at = timezone.now()
    if len(leaders) > 1:
        challenge.is_tie = True
        challenge.winner = None
    else:
        challenge.is_tie = False
        challenge.winner = leaders[0]
    challenge.save(update_fields=['status', 'resolved_at', 'is_tie', 'winner'])
    return challenge


@transaction.atomic
def finalize_tournament(tournament: Tournament):
    """
    The big one: locks in the leaderboard, resolves every outstanding
    challenge, and awards every tournament-flavoured badge that just became
    true. Safe to call more than once — e.g. after a teacher corrects a
    score — everything here is recomputed from scratch, not accumulated.
    """
    from mathapi.apps.gamification.services import evaluate_badges, get_student_progress
    from mathapi.apps.gamification.models import StudentStreak, QuizStreak

    entries = list(tournament.entries.filter(withdrawn=False).select_related('student', 'stream'))

    ranked = []
    for entry in entries:
        score = get_entry_score(entry)
        prior = get_prior_average(entry.student, exclude_exam=tournament.exam) if entry.student_id else None
        ranked.append({'entry': entry, 'score': score, 'prior': prior})

    # Highest score first; unscored entries (absent/never sat) sink to the bottom.
    ranked.sort(key=lambda r: (r['score'] is None, -(r['score'] or 0)))

    rank = 0
    last_score = object()
    for i, row in enumerate(ranked):
        if row['score'] != last_score:
            rank = i + 1
            last_score = row['score']
        row['rank'] = rank if row['score'] is not None else None

    for row in ranked:
        entry, score, prior = row['entry'], row['score'], row['prior']
        delta = round(score - prior, 2) if (score is not None and prior is not None) else None
        is_rising = bool(delta is not None and delta >= RISING_STAR_DELTA)
        is_champion = row['rank'] == 1 and score is not None
        EntryResult.objects.update_or_create(
            entry=entry,
            defaults={
                'score_percentage': score, 'rank': row['rank'], 'prior_average': prior,
                'delta': delta, 'is_rising_star': is_rising, 'is_champion': is_champion,
                'is_absent': score is None,
            },
        )

    # Resolve every outstanding challenge now that scores are in.
    for challenge in tournament.challenges.filter(status=Challenge.Status.PENDING):
        resolve_challenge(challenge)

    tournament.status = Tournament.Status.COMPLETED
    tournament.finalized_at = timezone.now()
    tournament.save(update_fields=['status', 'finalized_at'])

    _award_tournament_badges(tournament)

    return get_tournament_dossier(tournament)


def _award_tournament_badges(tournament: Tournament):
    """Recomputes lifetime tournament stats for every student touched by this
    tournament and awards any newly-earned badges. Stream entries don't have
    a single student to award, so only individual-mode participation and any
    students inside a stream-mode entry's own head-to-head duels count."""
    from mathapi.apps.gamification.services import evaluate_badges
    from mathapi.apps.gamification.models import StudentStreak, QuizStreak

    student_ids = set(
        tournament.entries.filter(student__isnull=False).values_list('student_id', flat=True)
    )
    # Students who fought in a duel as part of a stream entry still deserve
    # individual duel-based badges — pull them in via challenge participants.
    for challenge in tournament.challenges.all():
        for entry in challenge.entries.filter(student__isnull=False):
            student_ids.add(entry.student_id)

    for student_id in student_ids:
        _award_for_student(student_id)


def _award_for_student(student_id):
    from mathapi.apps.students.models import StudentProfile
    from mathapi.apps.gamification.services import evaluate_badges

    try:
        student = StudentProfile.objects.get(id=student_id)
    except StudentProfile.DoesNotExist:
        return []

    my_entries = TournamentEntry.objects.filter(student=student, withdrawn=False)
    participations = my_entries.values('tournament').distinct().count()
    titles = EntryResult.objects.filter(entry__student=student, is_champion=True).count()

    won_challenges = Challenge.objects.filter(winner__student=student, status=Challenge.Status.RESOLVED)
    match_wins = won_challenges.count()

    is_undefeated = False
    for tid in my_entries.values_list('tournament_id', flat=True).distinct():
        fought = Challenge.objects.filter(tournament_id=tid, entries__student=student,
                                           status=Challenge.Status.RESOLVED)
        total_fought = fought.count()
        if total_fought >= 2 and fought.filter(winner__student=student).count() == total_fought:
            is_undefeated = True
            break

    is_giant_slayer = False
    is_flawless = False
    is_underdog = False
    for challenge in won_challenges.select_related('winner'):
        winner_entry = challenge.winner
        opponents = challenge.entries.exclude(id=winner_entry.id)
        winner_seed = winner_entry.seed_average
        winner_score = get_entry_score(winner_entry)
        if winner_score is not None and winner_score >= 100:
            is_flawless = True
        for opp in opponents:
            if winner_seed is not None and opp.seed_average is not None:
                if opp.seed_average - winner_seed >= GIANT_SLAYER_GAP:
                    is_giant_slayer = True
                if opp.seed_average > winner_seed:
                    is_underdog = True

    is_rising_star = EntryResult.objects.filter(entry__student=student, is_rising_star=True).exists()

    return evaluate_badges(
        student,
        tournament_participations=participations,
        tournament_match_wins=match_wins,
        tournament_titles=titles,
        is_tournament_undefeated=is_undefeated,
        is_giant_slayer=is_giant_slayer,
        is_tournament_rising_star=is_rising_star,
        is_flawless_duel=is_flawless,
        is_underdog=is_underdog,
    )


def get_student_tournament_stats(student_id) -> dict:
    """Lightweight read-only summary of a student's tournament record —
    used by the report engines (PDF/Excel) to show tournament prizes
    alongside badges. Same counts as _award_for_student() computes, but
    without any badge side-effects."""
    participations = (
        TournamentEntry.objects.filter(student_id=student_id, withdrawn=False)
        .values('tournament').distinct().count()
    )
    titles = EntryResult.objects.filter(entry__student_id=student_id, is_champion=True).count()
    match_wins = Challenge.objects.filter(
        winner__student_id=student_id, status=Challenge.Status.RESOLVED,
    ).count()
    rising_star_count = EntryResult.objects.filter(entry__student_id=student_id, is_rising_star=True).count()
    return {
        'participations': participations,
        'titles': titles,
        'match_wins': match_wins,
        'rising_star_count': rising_star_count,
    }


def get_tournament_dossier(tournament: Tournament) -> dict:
    """Everything the intel/analytics view needs in one shot: ranked
    leaderboard, resolved/pending challenges, and headline callouts
    (champion + rising stars) — the 'never miss a bit of info' payload."""
    results = (
        EntryResult.objects.filter(entry__tournament=tournament)
        .select_related('entry', 'entry__student', 'entry__student__user', 'entry__stream', 'entry__stream__classroom')
        .order_by('rank')
    )
    champion = next((r for r in results if r.is_champion), None)
    rising_stars = [r for r in results if r.is_rising_star]
    return {
        'tournament': tournament,
        'results': list(results),
        'champion': champion,
        'rising_stars': rising_stars,
    }
