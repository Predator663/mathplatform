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
LEVEL_COMPATIBILITY_GAP = 15.0  # percentage points apart before two entrants count as "different level"


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

    newly_awarded = _award_tournament_badges(tournament)

    return get_tournament_dossier(tournament, newly_awarded_badges=newly_awarded)


def _award_tournament_badges(tournament: Tournament) -> dict:
    """Recomputes lifetime tournament stats for every student touched by this
    tournament and awards any newly-earned badges. Stream entries don't have
    a single student to award, so only individual-mode participation and any
    students inside a stream-mode entry's own head-to-head duels count.
    Returns {student_id: [Badge, ...]} of badges newly awarded THIS run, so
    callers (e.g. the result-announcement email) can say "you just earned
    X" rather than listing a student's entire lifetime collection."""
    student_ids = set(
        tournament.entries.filter(student__isnull=False).values_list('student_id', flat=True)
    )
    # Students who fought in a duel as part of a stream entry still deserve
    # individual duel-based badges — pull them in via challenge participants.
    for challenge in tournament.challenges.all():
        for entry in challenge.entries.filter(student__isnull=False):
            student_ids.add(entry.student_id)

    newly_awarded = {}
    for student_id in student_ids:
        awarded = _award_for_student(student_id)
        if awarded:
            newly_awarded[student_id] = [sb.badge for sb in awarded]
    return newly_awarded


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


SCORE_BANDS = [
    ('0-39', 0, 39.999),
    ('40-59', 40, 59.999),
    ('60-74', 60, 74.999),
    ('75-89', 75, 89.999),
    ('90-100', 90, 100.0001),
]


def get_tournament_analytics(tournament: Tournament) -> dict:
    """
    The 'never miss a bit of info' analytics payload for a single
    tournament: score distribution, participation rate against the whole
    classroom, entrant average vs. classroom-wide average on the same
    exam, pass rate, and headline callouts (closest duel, biggest upset,
    top riser). Only meaningful once the tournament is finalized — returns
    a mostly-empty shell before that so the frontend can show a clean
    'not finalized yet' state instead of misleading zeros.
    """
    from mathapi.apps.students.models import StudentProfile

    results = list(
        EntryResult.objects.filter(entry__tournament=tournament)
        .select_related('entry', 'entry__student', 'entry__stream')
    )
    classroom_size = StudentProfile.objects.filter(classroom=tournament.classroom, is_active=True).count()
    entrant_count = tournament.entries.filter(withdrawn=False).count()
    participation_rate = round((entrant_count / classroom_size) * 100, 1) if classroom_size else None

    scored = [r for r in results if r.score_percentage is not None]
    distribution = []
    for label, lo, hi in SCORE_BANDS:
        count = sum(1 for r in scored if lo <= r.score_percentage <= hi)
        distribution.append({'band': label, 'count': count})

    entrant_avg = round(sum(r.score_percentage for r in scored) / len(scored), 2) if scored else None
    pass_mark = float(tournament.exam.passing_score / tournament.exam.max_score * 100) if tournament.exam.max_score else 40
    pass_rate = round(sum(1 for r in scored if r.score_percentage >= pass_mark) / len(scored) * 100, 1) if scored else None
    absentee_count = sum(1 for r in results if r.is_absent)

    classroom_scores = list(
        ExamScore.objects.filter(exam=tournament.exam, student__classroom=tournament.classroom, is_absent=False)
        .values_list('score', flat=True)
    )
    classroom_avg = None
    if classroom_scores and tournament.exam.max_score:
        pct_scores = [float(s) / float(tournament.exam.max_score) * 100 for s in classroom_scores]
        classroom_avg = round(sum(pct_scores) / len(pct_scores), 2)

    resolved_challenges = list(
        tournament.challenges.filter(status=Challenge.Status.RESOLVED)
        .prefetch_related('entries__student', 'entries__stream')
        .select_related('winner')
    )
    closest_duel, closest_gap = None, None
    biggest_upset, biggest_upset_gap = None, None
    for c in resolved_challenges:
        entry_scores = [(e, get_entry_score(e)) for e in c.entries.all()]
        entry_scores = [(e, s) for e, s in entry_scores if s is not None]
        if len(entry_scores) < 2:
            continue
        entry_scores.sort(key=lambda pair: pair[1], reverse=True)
        gap = round(entry_scores[0][1] - entry_scores[1][1], 2)
        if closest_gap is None or gap < closest_gap:
            closest_gap, closest_duel = gap, c
        if c.winner and c.winner.seed_average is not None:
            loser_seeds = [e.seed_average for e, _ in entry_scores if e.id != c.winner.id and e.seed_average is not None]
            if loser_seeds:
                seed_gap = max(loser_seeds) - c.winner.seed_average
                if seed_gap > 0 and (biggest_upset_gap is None or seed_gap > biggest_upset_gap):
                    biggest_upset_gap, biggest_upset = seed_gap, c

    top_riser = max((r for r in results if r.delta is not None), key=lambda r: r.delta, default=None)

    return {
        'entrant_count': entrant_count,
        'classroom_size': classroom_size,
        'participation_rate': participation_rate,
        'absentee_count': absentee_count,
        'score_distribution': distribution,
        'entrant_average': entrant_avg,
        'classroom_average': classroom_avg,
        'pass_rate': pass_rate,
        'closest_duel': {
            'challenge_id': closest_duel.id, 'label': closest_duel.label, 'gap': closest_gap,
        } if closest_duel else None,
        'biggest_upset': {
            'challenge_id': biggest_upset.id, 'label': biggest_upset.label,
            'winner': biggest_upset.winner.display_name, 'seed_gap': round(biggest_upset_gap, 2),
        } if biggest_upset else None,
        'top_riser': {
            'name': top_riser.entry.display_name, 'delta': top_riser.delta,
        } if top_riser and top_riser.delta and top_riser.delta > 0 else None,
    }


def check_entry_compatibility(entry_a: TournamentEntry, entry_b: TournamentEntry) -> dict:
    """
    Are these two entrants actually at the same level? Compares each
    student's historical average across EVERY previous published exam
    (not just seed_average, which was frozen at registration time and can
    go stale) and flags a pair as incompatible once the gap crosses
    LEVEL_COMPATIBILITY_GAP.

    This never blocks anything — a wide-gap duel is still a perfectly
    valid "giant slayer" story the badge system already rewards — it's
    purely informational, surfaced so a teacher can choose to re-pair a
    lopsided matchup via auto_create_compatible_challenges() instead.

    Only meaningful for two individual (student) entries; stream entries
    return compatible=None since "level" isn't a single number for a
    whole stream in the same sense.
    """
    if not entry_a.student_id or not entry_b.student_id:
        return {
            'compatible': None, 'gap': None, 'threshold': LEVEL_COMPATIBILITY_GAP,
            'reason': 'Compatibility is only evaluated for student-vs-student entries.',
            'entry_a': {'id': entry_a.id, 'name': entry_a.display_name, 'average': None},
            'entry_b': {'id': entry_b.id, 'name': entry_b.display_name, 'average': None},
        }

    avg_a = get_prior_average(entry_a.student, exclude_exam=entry_a.tournament.exam)
    avg_b = get_prior_average(entry_b.student, exclude_exam=entry_b.tournament.exam)

    if avg_a is None or avg_b is None:
        missing = entry_a.display_name if avg_a is None else entry_b.display_name
        return {
            'compatible': None, 'gap': None, 'threshold': LEVEL_COMPATIBILITY_GAP,
            'reason': f'{missing} has no prior exam history yet, so capability cannot be judged.',
            'entry_a': {'id': entry_a.id, 'name': entry_a.display_name, 'average': avg_a},
            'entry_b': {'id': entry_b.id, 'name': entry_b.display_name, 'average': avg_b},
        }

    gap = round(abs(avg_a - avg_b), 2)
    compatible = gap <= LEVEL_COMPATIBILITY_GAP
    return {
        'compatible': compatible, 'gap': gap, 'threshold': LEVEL_COMPATIBILITY_GAP,
        'reason': None if compatible else f'{gap} percentage points apart on average — different skill levels.',
        'entry_a': {'id': entry_a.id, 'name': entry_a.display_name, 'average': avg_a},
        'entry_b': {'id': entry_b.id, 'name': entry_b.display_name, 'average': avg_b},
    }


def check_challenge_compatibility(challenge: Challenge) -> dict | None:
    """Same check as check_entry_compatibility, but for an already-created
    two-entry Challenge. Returns None for challenges that aren't a clean
    student-vs-student pair (byes, 3+-way, stream duels)."""
    entries = list(challenge.entries.select_related('student', 'stream', 'tournament__exam').all())
    if len(entries) != 2:
        return None
    return check_entry_compatibility(entries[0], entries[1])


def _pair_adjacent(ranked: list) -> list:
    """ranked: list of (entry, avg) sorted descending, even length. Pairs
    strictly consecutively — the arrangement that minimises every pair's
    gap simultaneously for a FIXED, already-sorted list."""
    pairs = []
    for i in range(0, len(ranked) - 1, 2):
        pairs.append((ranked[i], ranked[i + 1]))
    return pairs


def suggest_compatible_pairs(tournament: Tournament) -> dict:
    """
    Looks at every individual entrant who isn't already in a challenge and
    proposes same-level 1-v-1 pairings from their historical averages
    (every previous published exam, same source as get_prior_average).

    Strategy: sort entrants by average descending, then pair adjacent
    students. With an odd number of entrants, someone has to sit out —
    rather than always benching the lowest scorer (which can force a
    lopsided pair elsewhere, e.g. when the odd one out sits in the middle
    of a tightly-clustered tier), every possible bye candidate is tried
    and whichever leaves the smallest total gap across all resulting
    pairs is kept. For typical classroom-sized tournaments this exhaustive
    check is cheap (O(n^2) comparisons on a few dozen entrants at most).

    Returns proposed pairs (each tagged compatible/not, same as
    check_entry_compatibility), the student sitting out as a bye, and
    students excluded for having no exam history to seed a level from —
    nothing here is written to the database; see
    auto_create_compatible_challenges for that.
    """
    unpaired_entries = list(
        tournament.entries.filter(withdrawn=False, student__isnull=False, challenges__isnull=True)
        .select_related('student', 'tournament__exam')
    )

    ranked = []
    insufficient_history = []
    for entry in unpaired_entries:
        avg = get_prior_average(entry.student, exclude_exam=tournament.exam)
        if avg is None:
            insufficient_history.append({'entry_id': entry.id, 'student_id': entry.student_id, 'name': entry.display_name})
        else:
            ranked.append((entry, avg))

    ranked.sort(key=lambda pair: pair[1], reverse=True)

    best_pairs, best_bye = [], None
    if len(ranked) % 2 == 0:
        best_pairs = _pair_adjacent(ranked)
    elif len(ranked) == 1:
        best_bye = ranked[0]
    elif ranked:
        best_total_gap = None
        for skip_idx in range(len(ranked)):
            remaining = ranked[:skip_idx] + ranked[skip_idx + 1:]
            candidate_pairs = _pair_adjacent(remaining)
            total_gap = sum(abs(a - b) for (_, a), (_, b) in candidate_pairs)
            if best_total_gap is None or total_gap < best_total_gap:
                best_total_gap, best_pairs, best_bye = total_gap, candidate_pairs, ranked[skip_idx]

    pairs = []
    for (entry_a, avg_a), (entry_b, avg_b) in best_pairs:
        gap = round(abs(avg_a - avg_b), 2)
        pairs.append({
            'entry_a': {'id': entry_a.id, 'student_id': entry_a.student_id, 'name': entry_a.display_name, 'average': avg_a},
            'entry_b': {'id': entry_b.id, 'student_id': entry_b.student_id, 'name': entry_b.display_name, 'average': avg_b},
            'gap': gap,
            'compatible': gap <= LEVEL_COMPATIBILITY_GAP,
        })

    bye = None
    if best_bye is not None:
        entry, avg = best_bye
        bye = {'entry_id': entry.id, 'student_id': entry.student_id, 'name': entry.display_name, 'average': avg}

    return {
        'proposed_pairs': pairs,
        'bye': bye,
        'insufficient_history': insufficient_history,
        'threshold': LEVEL_COMPATIBILITY_GAP,
    }


@transaction.atomic
def auto_create_compatible_challenges(tournament: Tournament, *, created_by=None, only_compatible=True) -> dict:
    """
    Materializes suggest_compatible_pairs() into real Challenge rows.
    With only_compatible=True (the default), pairs whose gap still
    exceeds LEVEL_COMPATIBILITY_GAP after best-effort adjacent pairing are
    left uncreated (e.g. a lone high-flyer with no similarly-strong peer
    left to pair against) so a teacher can review and pair them manually
    instead of forcing a mismatch. Pass only_compatible=False to pair
    everyone regardless of gap size.
    """
    suggestion = suggest_compatible_pairs(tournament)
    created = []
    skipped = []
    for pair in suggestion['proposed_pairs']:
        if only_compatible and not pair['compatible']:
            skipped.append(pair)
            continue
        entry_a_id, entry_b_id = pair['entry_a']['id'], pair['entry_b']['id']
        entries = TournamentEntry.objects.filter(id__in=[entry_a_id, entry_b_id])
        challenge = Challenge.objects.create(
            tournament=tournament,
            label=f"Level Match — {pair['entry_a']['name']} vs {pair['entry_b']['name']}",
            initiated_by=created_by,
        )
        challenge.entries.set(entries)
        created.append(challenge)

    return {
        'created': created,
        'skipped_incompatible': skipped,
        'bye': suggestion['bye'],
        'insufficient_history': suggestion['insufficient_history'],
    }


def get_head_to_head(student_a_id, student_b_id) -> dict:
    """Every resolved challenge these two students have ever fought,
    across every tournament — a lifetime rivalry record."""
    from mathapi.apps.students.models import StudentProfile

    challenges = (
        Challenge.objects.filter(
            status=Challenge.Status.RESOLVED,
            entries__student_id=student_a_id,
        )
        .filter(entries__student_id=student_b_id)
        .distinct()
        .select_related('tournament', 'winner', 'winner__student')
        .order_by('-resolved_at')
    )
    # Guard against pulling in 3+-way challenges that merely include both students
    # incidentally — a head-to-head record should only count duels that were
    # exactly these two.
    exact = [c for c in challenges if set(c.entries.values_list('student_id', flat=True)) == {student_a_id, student_b_id}]

    a_wins = sum(1 for c in exact if c.winner and c.winner.student_id == student_a_id)
    b_wins = sum(1 for c in exact if c.winner and c.winner.student_id == student_b_id)
    ties = sum(1 for c in exact if c.is_tie)

    try:
        student_a = StudentProfile.objects.get(id=student_a_id)
        student_b = StudentProfile.objects.get(id=student_b_id)
    except StudentProfile.DoesNotExist:
        return {'error': 'One or both students not found.'}

    return {
        'student_a': {'id': student_a.id, 'name': student_a.full_name},
        'student_b': {'id': student_b.id, 'name': student_b.full_name},
        'a_wins': a_wins, 'b_wins': b_wins, 'ties': ties, 'total_duels': len(exact),
        'history': [
            {
                'challenge_id': c.id, 'tournament': c.tournament.title,
                'label': c.label, 'winner': c.winner.display_name if c.winner else None,
                'is_tie': c.is_tie, 'resolved_at': c.resolved_at.isoformat() if c.resolved_at else None,
            }
            for c in exact
        ],
    }


def get_tournament_dossier(tournament: Tournament, newly_awarded_badges: dict = None) -> dict:
    """Everything the intel/analytics view needs in one shot: ranked
    leaderboard, resolved/pending challenges, and headline callouts
    (champion + rising stars) — the 'never miss a bit of info' payload.

    `newly_awarded_badges` — optional {student_id: [Badge, ...]}, passed
    straight through from finalize_tournament() so the result-announcement
    email can list exactly what was just earned."""
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
        'newly_awarded_badges': newly_awarded_badges or {},
    }
