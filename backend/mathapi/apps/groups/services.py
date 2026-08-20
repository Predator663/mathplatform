"""
Peer-group computation — performance tiering, balanced auto-generation,
and the rule checks used by manual transfers.
"""
from collections import defaultdict
from django.db.models import Q
from mathapi.apps.exams.models import ExamScore
from mathapi.apps.students.models import StudentProfile
from .models import PerformanceTier, PeerConstraint, GroupMembership, StudentGroup

# Score-percentage buckets used for group-assignment distribution charts —
# kept identical to the bucket edges the analytics frontend already uses
# for individual exam distributions, so a "60-69%" bar means the same
# thing everywhere in the app.
SCORE_BUCKETS = [
    (0, 49, '0-49'), (50, 59, '50-59'), (60, 69, '60-69'),
    (70, 79, '70-79'), (80, 89, '80-89'), (90, 100, '90-100'),
]

# How far below the classroom-wide average a group's average has to fall
# (in percentage points) before it's flagged as needing a reassignment
# look — matches the 20-point band used elsewhere in the app (e.g. C-to-A
# is a 30-point spread) to avoid flagging normal variance.
UNDERPERFORMING_GAP = 12.0


def _bucket_for(pct: float) -> str:
    for lo, hi, label in SCORE_BUCKETS:
        if lo <= pct <= hi:
            return label
    return SCORE_BUCKETS[-1][2]

# Mirrors ExamScore.letter_grade / reports engines exactly (see models.py
# docstring on PerformanceTier) — do not drift these numbers apart.
TIER_THRESHOLDS = (
    (75, PerformanceTier.VERY_STRONG),
    (65, PerformanceTier.STRONG),
    (45, PerformanceTier.AVERAGE),
    (0,  PerformanceTier.WEAK),
)

# Tiers counted as capable of anchoring/mentoring a group.
ANCHOR_TIERS = {PerformanceTier.VERY_STRONG, PerformanceTier.STRONG}

# Ordinal ranking of tiers, weakest to strongest, for measuring drift
# direction/magnitude between a student's tier at placement and their
# current live tier. UNRATED sits below WEAK — going from unrated to any
# rated tier isn't drift, it's just data arriving, so it's excluded
# explicitly in get_rebalance_suggestions rather than relying on this order.
TIER_ORDER = {
    PerformanceTier.UNRATED: -1,
    PerformanceTier.WEAK: 0,
    PerformanceTier.AVERAGE: 1,
    PerformanceTier.STRONG: 2,
    PerformanceTier.VERY_STRONG: 3,
}


def tier_for_average(average: float | None) -> str:
    if average is None:
        return PerformanceTier.UNRATED
    for threshold, tier in TIER_THRESHOLDS:
        if average >= threshold:
            return tier
    return PerformanceTier.WEAK


def get_classroom_student_performance(
    classroom_id: int,
    subject_id: int = None,
    term: str = None,
    academic_year: str = None,
    created_by_id: int = None,
    stream_id: int = None,
) -> list[dict]:
    """
    One row per active student in the classroom: average %, exams taken,
    and performance tier. Students with no scores yet still appear
    (tier='unrated') so they're visible on the grouping page instead of
    silently vanishing.

    `stream_id`, if given, narrows the roster to students placed in that
    one stream (e.g. Form 2 "A") — the same filter auto-generate uses to
    build stream-only groups. Every row also carries the student's own
    stream_id/stream_name regardless, so callers that don't filter can
    still display or group by stream.
    """
    students = (
        StudentProfile.objects.filter(classroom_id=classroom_id, is_active=True)
        .select_related('user', 'stream')
        .order_by('user__first_name', 'user__last_name')
    )
    if stream_id:
        students = students.filter(stream_id=stream_id)

    filters = Q(student__classroom_id=classroom_id, is_absent=False)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if term:
        filters &= Q(exam__term=term)
    if academic_year:
        filters &= Q(exam__academic_year=academic_year)
    if created_by_id:
        # Same isolation rule as analytics.services — a teacher only ever
        # ranks/groups students against exams *they* created.
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('exam')
    by_student = defaultdict(list)
    for s in scores:
        by_student[s.student_id].append(s.percentage)

    rows = []
    for sp in students:
        pcts = by_student.get(sp.id, [])
        average = round(sum(pcts) / len(pcts), 1) if pcts else None
        rows.append({
            'student_id': sp.id,
            'student_name': sp.full_name,
            'student_code': sp.student_id,
            'average': average,
            'exams_taken': len(pcts),
            'tier': tier_for_average(average),
            'stream_id': sp.stream_id,
            'stream_name': sp.stream.name if sp.stream_id else None,
        })

    rows.sort(key=lambda r: (r['average'] is None, -(r['average'] or 0)))
    return rows


def plan_balanced_groups(
    students: list[dict],
    group_count: int = None,
    group_size: int = None,
) -> dict:
    """
    Split `students` (as returned by get_classroom_student_performance,
    already sorted strongest-first) into balanced groups using a snake
    ("serpentine") draft: group 1 gets the strongest student, group 2 the
    next, ... last group gets the Nth, then the direction reverses for the
    (N+1)th strongest, and so on. This is the standard technique for
    balancing teams by skill because:
      - every group gets a turn near the top of the draft order, so as
        long as there are at least as many strong/very-strong students as
        groups, every group is guaranteed at least one anchor student.
      - group averages end up close to each other, because each "lap" of
        the snake hands out one high scorer and one low scorer per group.

    Returns {'groups': [[student_dict, ...], ...], 'warnings': [str, ...]}.
    """
    warnings: list[str] = []
    n = len(students)
    if n == 0:
        return {'groups': [], 'warnings': ['No active students in this classroom to group.']}

    anchors = [s for s in students if s['tier'] in ANCHOR_TIERS]

    if group_count and group_count > 0:
        g = group_count
    elif group_size and group_size > 0:
        g = max(1, -(-n // group_size))  # ceil division
    else:
        # Default: one group per available anchor student, so "every group
        # has at least one strong/very-strong student" holds automatically.
        g = max(1, len(anchors))

    if len(anchors) == 0:
        warnings.append(
            'No students currently rank as Strong or Very Strong (average ≥ 65%), '
            'so groups could not be guaranteed a peer mentor. Groups were still '
            'balanced by whatever performance data is available.'
        )
    elif g > len(anchors):
        warnings.append(
            f'Requested {g} groups, but only {len(anchors)} student(s) qualify as '
            f'Strong/Very Strong — capped to {len(anchors)} group(s) so every group '
            f'still gets at least one strong peer.'
        )
        g = len(anchors)

    g = min(g, n)  # never more groups than students
    g = max(g, 1)

    groups: list[list[dict]] = [[] for _ in range(g)]
    direction = 1
    idx = 0
    for student in students:
        groups[idx].append(student)
        if direction == 1 and idx == g - 1:
            direction = -1
        elif direction == -1 and idx == 0:
            direction = 1
        else:
            idx += direction

    sizes = [len(gr) for gr in groups]
    if sizes and (max(sizes) - min(sizes) > 1):
        warnings.append('Group sizes could not be perfectly balanced given the student count.')

    for gr in groups:
        if not any(s['tier'] in ANCHOR_TIERS for s in gr):
            warnings.append(
                f'A group has no Strong/Very Strong student available — '
                f'not enough anchor students to cover every group.'
            )
            break

    return {'groups': groups, 'warnings': warnings}


def get_group_effectiveness(
    classroom_id: int,
    academic_year: str = None,
    subject_id: int = None,
    term: str = None,
    created_by_id: int = None,
    stream_id: int = None,
) -> dict:
    """
    Measures whether peer groups are actually helping, not just whether
    they're balanced: for each member, compares their average *since
    joining* the group against `average_at_placement` (the average they
    had the moment they were placed). A positive delta means they've
    improved since being grouped.

    "Since joining" is scored only from exams dated on/after the
    membership's joined_at, so a group's number isn't diluted by scores
    that predate the current grouping round.

    Returns per-student deltas, a per-group rollup, and a classroom-wide
    rollup that also splits anchors vs non-anchors — the latter is what
    tells you whether the "pair strong with weak" theory is actually
    paying off for this classroom, not just an assumption.
    """
    from .models import StudentGroup

    groups = (
        StudentGroup.objects.filter(classroom_id=classroom_id, academic_year=academic_year)
        .prefetch_related('memberships__student__user')
        .order_by('name')
    )
    if stream_id:
        groups = groups.filter(stream_id=stream_id)

    base_filters = Q(student__classroom_id=classroom_id, is_absent=False)
    if subject_id:
        base_filters &= Q(exam__subject_id=subject_id)
    if term:
        base_filters &= Q(exam__term=term)
    if academic_year:
        base_filters &= Q(exam__academic_year=academic_year)
    if created_by_id:
        base_filters &= Q(exam__created_by_id=created_by_id)

    result_groups = []
    anchor_deltas, non_anchor_deltas = [], []

    for group in groups:
        member_rows = []
        group_deltas = []
        for m in group.memberships.all():
            scores = ExamScore.objects.filter(
                base_filters, student_id=m.student_id, exam__exam_date__gte=m.joined_at.date(),
            ).select_related('exam')
            pcts = [s.percentage for s in scores]
            current_avg = round(sum(pcts) / len(pcts), 1) if pcts else None
            delta = None
            if current_avg is not None and m.average_at_placement is not None:
                delta = round(current_avg - m.average_at_placement, 1)

            member_rows.append({
                'student_id': m.student_id,
                'student_name': m.student.full_name,
                'tier_at_placement': m.tier,
                'average_at_placement': m.average_at_placement,
                'current_average_since_joining': current_avg,
                'exams_since_joining': len(pcts),
                'delta': delta,
                'is_anchor': m.is_anchor,
            })
            if delta is not None:
                group_deltas.append(delta)
                (anchor_deltas if m.is_anchor else non_anchor_deltas).append(delta)

        member_rows.sort(key=lambda r: (r['delta'] is None, -(r['delta'] or -999)))
        result_groups.append({
            'group_id': group.id,
            'group_name': group.name,
            'member_count': len(member_rows),
            'members': member_rows,
            'average_delta': round(sum(group_deltas) / len(group_deltas), 1) if group_deltas else None,
            'has_sufficient_data': len(group_deltas) > 0,
        })

    result_groups.sort(key=lambda g: (g['average_delta'] is None, -(g['average_delta'] or -999)))
    all_deltas = anchor_deltas + non_anchor_deltas

    return {
        'groups': result_groups,
        'classroom_average_delta': round(sum(all_deltas) / len(all_deltas), 1) if all_deltas else None,
        'anchor_average_delta': round(sum(anchor_deltas) / len(anchor_deltas), 1) if anchor_deltas else None,
        'non_anchor_average_delta': round(sum(non_anchor_deltas) / len(non_anchor_deltas), 1) if non_anchor_deltas else None,
        'students_with_data': len(all_deltas),
    }


def get_rebalance_suggestions(
    classroom_id: int,
    academic_year: str = None,
    subject_id: int = None,
    term: str = None,
    created_by_id: int = None,
    stream_id: int = None,
) -> dict:
    """
    Flags where groups have drifted out of balance since they were formed,
    using *live* tiers (recomputed from all current scores) against the
    tier each student was placed at. Nothing here is applied automatically
    — it's a suggestion queue a teacher reviews and actions manually via
    the existing transfer endpoint, same non-blocking philosophy as
    check_transfer_warnings.

    Two kinds of findings:
      - tier_changes: students whose live tier no longer matches the tier
        they were placed at (promotions and drops alike).
      - groups_needing_attention: groups that currently have zero members
        in an anchor tier *right now* (regardless of who was an anchor at
        placement), with candidate students to move in — anchor-tier
        students who belong to a different group that currently has more
        than one anchor, so moving them doesn't just break that group.
    """
    from .models import StudentGroup

    performance = get_classroom_student_performance(
        classroom_id, subject_id=subject_id, term=term,
        academic_year=academic_year, created_by_id=created_by_id, stream_id=stream_id,
    )
    live_tier_by_student = {p['student_id']: p for p in performance}

    groups = (
        StudentGroup.objects.filter(classroom_id=classroom_id, academic_year=academic_year)
        .prefetch_related('memberships__student__user')
        .order_by('name')
    )
    if stream_id:
        groups = groups.filter(stream_id=stream_id)

    tier_changes = []
    group_live_anchors = {}   # group_id -> [membership dicts currently anchor-tier]
    group_members_live = {}   # group_id -> [ (membership, live_row) ]

    for group in groups:
        live_anchors, members_live = [], []
        for m in group.memberships.all():
            live = live_tier_by_student.get(m.student_id)
            if not live:
                continue
            members_live.append((m, live))
            if live['tier'] in ANCHOR_TIERS:
                live_anchors.append((m, live))

            placement_order = TIER_ORDER.get(m.tier, -1)
            live_order = TIER_ORDER.get(live['tier'], -1)
            if live['tier'] != m.tier and placement_order >= 0 and live_order >= 0:
                tier_changes.append({
                    'student_id': m.student_id,
                    'student_name': m.student.full_name,
                    'group_id': group.id,
                    'group_name': group.name,
                    'tier_at_placement': m.tier,
                    'current_tier': live['tier'],
                    'current_average': live['average'],
                    'direction': 'up' if live_order > placement_order else 'down',
                    'magnitude': abs(live_order - placement_order),
                })
        group_live_anchors[group.id] = live_anchors
        group_members_live[group.id] = members_live

    tier_changes.sort(key=lambda c: (-c['magnitude'], c['student_name']))

    groups_needing_attention = []
    for group in groups:
        if group_live_anchors[group.id]:
            continue  # has at least one current anchor, nothing to flag

        candidates = []
        for other in groups:
            if other.id == group.id or len(group_live_anchors[other.id]) <= 1:
                continue
            for m, live in group_live_anchors[other.id]:
                candidates.append({
                    'student_id': m.student_id,
                    'student_name': m.student.full_name,
                    'from_group_id': other.id,
                    'from_group_name': other.name,
                    'current_tier': live['tier'],
                    'current_average': live['average'],
                })
        candidates.sort(key=lambda c: -(c['current_average'] or 0))

        groups_needing_attention.append({
            'group_id': group.id,
            'group_name': group.name,
            'reason': 'No student currently ranks Strong or Very Strong in this group.',
            'candidates': candidates[:3],
        })

    return {
        'tier_changes': tier_changes,
        'groups_needing_attention': groups_needing_attention,
    }


def _pair_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def apply_peer_constraints(
    groups: list[list[dict]],
    avoid_pairs: set[tuple[int, int]],
    prefer_pairs: set[tuple[int, int]],
    name_by_id: dict[int, str] = None,
) -> list[str]:
    """
    Mutates `groups` (as produced by plan_balanced_groups) in place to
    resolve 'avoid' constraints and honour 'prefer' constraints via
    targeted single-student swaps between groups.

    Avoid constraints are treated as hard — resolved first, with a swap
    chosen to keep group averages close (nearest-average candidate) and
    never allowed to create a *new* avoid violation. Prefer constraints
    are honoured afterward on a best-effort basis and are allowed to fail
    quietly into a warning, since two students already violating an
    avoid constraint elsewhere always takes priority over convenience.

    Returns human-readable warnings for anything that couldn't be
    resolved without violating another constraint.
    """
    name_by_id = name_by_id or {}
    warnings: list[str] = []

    def label(pair: tuple[int, int]) -> str:
        a, b = pair
        return f'{name_by_id.get(a, a)} & {name_by_id.get(b, b)}'

    def index_of(student_id: int) -> int | None:
        for gi, g in enumerate(groups):
            if any(s['student_id'] == student_id for s in g):
                return gi
        return None

    def has_avoid(student_ids: set[int]) -> bool:
        for a in student_ids:
            for b in student_ids:
                if a < b and (a, b) in avoid_pairs:
                    return True
        return False

    def try_swap(student_id: int, from_gi: int, to_gi: int) -> bool:
        s_idx = next(i for i, s in enumerate(groups[from_gi]) if s['student_id'] == student_id)
        student = groups[from_gi][s_idx]
        # Try candidates nearest in average first, so the swap disturbs
        # group-balance as little as possible.
        ranked = sorted(groups[to_gi], key=lambda c: abs((c['average'] or 0) - (student['average'] or 0)))
        for cand in ranked:
            new_from = [s for s in groups[from_gi] if s['student_id'] != student_id] + [cand]
            new_to = [s for s in groups[to_gi] if s['student_id'] != cand['student_id']] + [student]
            new_from_ids = {s['student_id'] for s in new_from}
            new_to_ids = {s['student_id'] for s in new_to}
            if not has_avoid(new_from_ids) and not has_avoid(new_to_ids):
                groups[from_gi] = new_from
                groups[to_gi] = new_to
                return True
        return False

    for pair in sorted(avoid_pairs):
        a, b = pair
        gi_a, gi_b = index_of(a), index_of(b)
        if gi_a is None or gi_b is None or gi_a != gi_b:
            continue  # already apart, or one/both not in this grouping round
        resolved = any(
            try_swap(b, gi_a, other_gi)
            for other_gi in range(len(groups)) if other_gi != gi_a
        )
        if not resolved:
            warnings.append(f'Could not keep {label(pair)} apart without violating another constraint.')

    for pair in sorted(prefer_pairs):
        a, b = pair
        gi_a, gi_b = index_of(a), index_of(b)
        if gi_a is None or gi_b is None or gi_a == gi_b:
            continue
        if not try_swap(b, gi_b, gi_a):
            warnings.append(f'Could not place {label(pair)} together without breaking group balance.')

    return warnings


def check_transfer_warnings(source_group_members: list, dest_group_members: list, moving_student_id: int,
                             average_group_size: float = None) -> list[str]:
    """Non-blocking sanity checks run before a manual transfer is applied.

    Transfers are never hard-blocked by these — an admin/teacher may have
    good reasons (a personality conflict, a parent request, etc.) that no
    automatic rule can see — but the caller is told what balance rule the
    move affects so it isn't a silent surprise.
    """
    warnings = []
    remaining_source = [m for m in source_group_members if m.student_id != moving_student_id]
    if source_group_members and not any(m.tier in ANCHOR_TIERS for m in remaining_source):
        warnings.append('The source group will be left without a Strong/Very Strong student.')

    if average_group_size is not None:
        new_dest_size = len(dest_group_members) + 1
        if new_dest_size > average_group_size + 2:
            warnings.append('The destination group will be notably larger than the classroom average group size.')

    return warnings


# ── Group assignments: recording marks ──────────────────────────────────────

def record_group_assignment_scores(assignment, entries: list[dict], user) -> dict:
    """
    Upserts one GroupAssignmentScore per entry (`{group_id, score,
    is_absent, remarks, member_adjustments: [...]}`), and syncs a
    GroupAssignmentMemberMark for every *current* member of that group so
    the mark is recorded once per group but still queryable per student.

    `member_adjustments` is optional — omitting it just gives every
    member the group's raw score (adjustment=0), which is the normal
    "graded as a group" path. Passing entries for specific student_ids
    lets a teacher tune one student's mark without re-entering everyone.

    Returns {'scores': [GroupAssignmentScore, ...], 'errors': [str, ...]}
    — a bad group_id in one entry doesn't abort the whole batch.
    """
    from .models import GroupAssignmentScore, GroupAssignmentMemberMark

    valid_group_ids = set(
        StudentGroup.objects.filter(classroom_id=assignment.classroom_id).values_list('id', flat=True)
    )
    saved, errors = [], []

    for entry in entries:
        group_id = entry.get('group_id')
        if group_id not in valid_group_ids:
            errors.append(f'Group {group_id} does not belong to this classroom — skipped.')
            continue

        score_val = entry.get('score', 0) or 0
        is_absent = bool(entry.get('is_absent', False))
        group_score, _ = GroupAssignmentScore.objects.update_or_create(
            assignment=assignment, group_id=group_id,
            defaults={
                'score': 0 if is_absent else score_val,
                'is_absent': is_absent,
                'remarks': entry.get('remarks', ''),
                'entered_by': user,
            },
        )

        adjustments_by_student = {
            a['student_id']: a for a in entry.get('member_adjustments', []) if a.get('student_id')
        }
        member_ids = GroupMembership.objects.filter(group_id=group_id).values_list('student_id', flat=True)
        for student_id in member_ids:
            override = adjustments_by_student.get(student_id, {})
            GroupAssignmentMemberMark.objects.update_or_create(
                group_score=group_score, student_id=student_id,
                defaults={
                    'adjustment': override.get('adjustment', 0) or 0,
                    'is_excused': bool(override.get('is_excused', is_absent)),
                    'note': override.get('note', ''),
                },
            )
        saved.append(group_score)

    return {'scores': saved, 'errors': errors}


# ── Group assignments: analytics ────────────────────────────────────────────

def _group_assignment_score_filters(
    classroom_id, stream_id=None, group_id=None, subject_id=None, term=None,
    academic_year=None, assignment_type=None, date_from=None, date_to=None, created_by_id=None,
):
    filters = Q(assignment__classroom_id=classroom_id, is_absent=False)
    if stream_id:
        filters &= Q(group__stream_id=stream_id) | Q(group__stream__isnull=True)
    if group_id:
        filters &= Q(group_id=group_id)
    if subject_id:
        filters &= Q(assignment__subject_id=subject_id)
    if term:
        filters &= Q(assignment__term=term)
    if academic_year:
        filters &= Q(assignment__academic_year=academic_year)
    if assignment_type:
        filters &= Q(assignment__assignment_type=assignment_type)
    if date_from:
        filters &= Q(assignment__date_given__gte=date_from)
    if date_to:
        filters &= Q(assignment__date_given__lte=date_to)
    if created_by_id:
        filters &= Q(assignment__created_by_id=created_by_id)
    return filters


def get_group_assignment_analytics(
    classroom_id, stream_id=None, group_id=None, subject_id=None, term=None,
    academic_year=None, assignment_type=None, date_from=None, date_to=None, created_by_id=None,
) -> dict:
    """
    The data behind the dedicated Group Work Analytics page: classroom,
    per-stream, and per-group rollups, a chronological trend, and a
    score-distribution histogram — everything scoped by the same filters
    the page exposes (stream / group / subject / term / year / type /
    date range), so 'switch the stream filter' and 'export this view'
    always agree on what they're looking at.
    """
    from .models import GroupAssignmentScore

    filters = _group_assignment_score_filters(
        classroom_id, stream_id=stream_id, group_id=group_id, subject_id=subject_id, term=term,
        academic_year=academic_year, assignment_type=assignment_type,
        date_from=date_from, date_to=date_to, created_by_id=created_by_id,
    )
    scores = list(
        GroupAssignmentScore.objects.filter(filters)
        .select_related('assignment', 'group', 'group__stream')
        .order_by('assignment__date_given')
    )

    if not scores:
        return {
            'classroom_average_pct': None, 'assignments_count': 0, 'groups_scored_count': 0,
            'distribution': {label: 0 for *_ , label in SCORE_BUCKETS},
            'trend': [], 'per_group': [], 'per_stream': [],
            'top_groups': [], 'bottom_groups': [],
        }

    all_pcts = [s.percentage for s in scores]
    distribution = {label: 0 for *_, label in SCORE_BUCKETS}
    for pct in all_pcts:
        distribution[_bucket_for(pct)] += 1

    # ── Trend: one point per assignment, classroom-wide average that day ──
    by_assignment = defaultdict(list)
    assignment_meta = {}
    for s in scores:
        by_assignment[s.assignment_id].append(s.percentage)
        assignment_meta[s.assignment_id] = s.assignment
    trend = [
        {
            'assignment_id': aid,
            'title': assignment_meta[aid].title,
            'date': assignment_meta[aid].date_given.isoformat(),
            'assignment_type': assignment_meta[aid].assignment_type,
            'average_pct': round(sum(pcts) / len(pcts), 1),
            'groups_scored': len(pcts),
        }
        for aid, pcts in by_assignment.items()
    ]
    trend.sort(key=lambda t: t['date'])

    # ── Per-group rollup ────────────────────────────────────────────────
    by_group = defaultdict(list)
    group_meta = {}
    for s in scores:
        by_group[s.group_id].append(s)
        group_meta[s.group_id] = s.group
    per_group = []
    for gid, group_scores in by_group.items():
        pcts = [s.percentage for s in group_scores]
        g = group_meta[gid]
        group_trend = sorted(
            [{'assignment_id': s.assignment_id, 'title': s.assignment.title,
              'date': s.assignment.date_given.isoformat(), 'pct': s.percentage} for s in group_scores],
            key=lambda t: t['date'],
        )
        per_group.append({
            'group_id': gid, 'group_name': g.name,
            'stream_id': g.stream_id, 'stream_name': g.stream.name if g.stream_id else None,
            'assignments_count': len(pcts),
            'average_pct': round(sum(pcts) / len(pcts), 1),
            'best_pct': max(pcts), 'worst_pct': min(pcts),
            'trend': group_trend,
        })
    per_group.sort(key=lambda g: -g['average_pct'])

    # ── Per-stream rollup ───────────────────────────────────────────────
    by_stream = defaultdict(list)
    stream_names = {}
    for s in scores:
        sid = s.group.stream_id
        by_stream[sid].append(s.percentage)
        stream_names[sid] = s.group.stream.name if sid else 'No Stream'
    per_stream = [
        {
            'stream_id': sid, 'stream_name': stream_names[sid],
            'group_count': len({s.group_id for s in scores if s.group.stream_id == sid}),
            'assignments_scored': len(pcts),
            'average_pct': round(sum(pcts) / len(pcts), 1),
        }
        for sid, pcts in by_stream.items()
    ]
    per_stream.sort(key=lambda s: -s['average_pct'])

    return {
        'classroom_average_pct': round(sum(all_pcts) / len(all_pcts), 1),
        'assignments_count': len(by_assignment),
        'groups_scored_count': len(by_group),
        'distribution': distribution,
        'trend': trend,
        'per_group': per_group,
        'per_stream': per_stream,
        'top_groups': per_group[:5],
        'bottom_groups': sorted(per_group, key=lambda g: g['average_pct'])[:5],
    }


# ── Group assignments: performance-based reassignment ───────────────────────

def get_group_assignment_reassignment_suggestions(
    classroom_id, stream_id=None, subject_id=None, term=None,
    academic_year=None, assignment_type=None, created_by_id=None,
) -> dict:
    """
    Flags groups whose *group-assignment* average sits well below the
    classroom average and proposes individual students to move in —
    candidates are drawn from students in other, better-performing groups
    within the same stream who also rank Strong/Very Strong on their own
    individual exam performance, so a move raises the weak group's floor
    without just relocating the problem.

    Nothing here is applied automatically — the frontend actions a
    suggestion through the existing transfer-member endpoint, same
    advisory-only philosophy as get_rebalance_suggestions.
    """
    analytics = get_group_assignment_analytics(
        classroom_id, stream_id=stream_id, subject_id=subject_id, term=term,
        academic_year=academic_year, assignment_type=assignment_type, created_by_id=created_by_id,
    )
    classroom_avg = analytics['classroom_average_pct']
    per_group = analytics['per_group']

    groups_out = [
        {
            'group_id': g['group_id'], 'group_name': g['group_name'],
            'stream_id': g['stream_id'], 'stream_name': g['stream_name'],
            'average_pct': g['average_pct'], 'assignments_count': g['assignments_count'],
            'status': (
                'below_average' if classroom_avg is not None and g['average_pct'] < classroom_avg - UNDERPERFORMING_GAP
                else 'above_average' if classroom_avg is not None and g['average_pct'] > classroom_avg + UNDERPERFORMING_GAP
                else 'average'
            ),
        }
        for g in per_group
    ]

    if classroom_avg is None:
        return {'classroom_average_pct': None, 'groups': groups_out, 'underperforming': []}

    individual_performance = get_classroom_student_performance(
        classroom_id, subject_id=subject_id, term=term,
        academic_year=academic_year, created_by_id=created_by_id, stream_id=stream_id,
    )
    perf_by_student = {p['student_id']: p for p in individual_performance}

    # Which group each student currently sits in, restricted to the same
    # grouping round the analytics above are scoped to.
    memberships = GroupMembership.objects.filter(
        group__classroom_id=classroom_id
    ).select_related('group', 'student__user')
    if academic_year:
        memberships = memberships.filter(group__academic_year=academic_year)
    if stream_id:
        memberships = memberships.filter(Q(group__stream_id=stream_id) | Q(group__stream__isnull=True))
    members_by_group = defaultdict(list)
    for m in memberships:
        members_by_group[m.group_id].append(m)

    group_by_id = {g['group_id']: g for g in per_group}
    underperforming = []
    for g in groups_out:
        if g['status'] != 'below_average':
            continue
        gap = round(classroom_avg - g['average_pct'], 1)

        candidates = []
        for other_gid, other in group_by_id.items():
            if other_gid == g['group_id'] or other['average_pct'] <= classroom_avg:
                continue
            # A candidate must belong to the same stream (or the move is
            # meaningless — groups are stream-scoped in practice), and
            # rank Strong/Very Strong individually so moving them doesn't
            # just drag the destination group down instead.
            for m in members_by_group.get(other_gid, []):
                perf = perf_by_student.get(m.student_id)
                if not perf or perf['tier'] not in ANCHOR_TIERS:
                    continue
                if g['stream_id'] and m.student.stream_id and m.student.stream_id != g['stream_id']:
                    continue
                candidates.append({
                    'student_id': m.student_id, 'student_name': m.student.full_name,
                    'from_group_id': other_gid, 'from_group_name': other['group_name'],
                    'current_tier': perf['tier'], 'individual_average': perf['average'],
                })
        candidates.sort(key=lambda c: -(c['individual_average'] or 0))

        underperforming.append({
            'group_id': g['group_id'], 'group_name': g['group_name'],
            'stream_id': g['stream_id'], 'stream_name': g['stream_name'],
            'average_pct': g['average_pct'], 'gap_from_classroom_average': gap,
            'candidates': candidates[:3],
        })

    underperforming.sort(key=lambda u: -u['gap_from_classroom_average'])

    return {
        'classroom_average_pct': classroom_avg,
        'groups': groups_out,
        'underperforming': underperforming,
    }


# ── Seating chart generator ─────────────────────────────────────────────────

def _grid_dimensions(count: int, rows: int | None, cols: int | None) -> tuple[int, int]:
    import math
    if rows and cols:
        return rows, cols
    if cols:
        return math.ceil(count / cols) if count else 1, cols
    if rows:
        return rows, math.ceil(count / rows) if count else 1
    # Auto: a slightly-wider-than-tall grid reads naturally as classroom rows.
    cols = math.ceil(math.sqrt(count)) if count else 1
    rows = math.ceil(count / cols) if count else 1
    return rows, cols


def _neighbor_positions(row: int, col: int, rows: int, cols: int):
    """Up/down/left/right — diagonal neighbors are deliberately excluded;
    two desks diagonally apart aren't really 'next to' each other."""
    candidates = [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]
    return [(r, c) for r, c in candidates if 0 <= r < rows and 0 <= c < cols]


def generate_seating_chart(
    classroom, *, stream_id: int = None, group_id: int = None,
    rows: int = None, cols: int = None,
) -> dict:
    """
    Builds a rows x cols seating grid for a classroom (optionally narrowed
    to one Stream or one StudentGroup), honoring standing PeerConstraint
    rules from that classroom:

    - AVOID pairs are kept out of directly-adjacent seats (up/down/left/right)
      wherever the grid has room to do so.
    - PREFER pairs are seated in an adjacent seat wherever possible.

    Group membership (StudentGroup / GroupMembership) is used as a
    secondary signal — students in the same group are clustered near each
    other in the placement order — but PREFER/AVOID constraints always take
    priority, since those are the explicit, standing rule.

    Returns a dict with `rows`, `cols`, `seats` (list of
    {row, col, student} or {row, col, student: None} for empty desks),
    `unseated` (students who didn't fit if the grid is too small), and
    `warnings` (any AVOID pairs that ended up adjacent anyway because the
    grid was too cramped to avoid it).
    """
    students_qs = StudentProfile.objects.filter(classroom=classroom, is_active=True).select_related('user')
    if stream_id:
        students_qs = students_qs.filter(stream_id=stream_id)
    if group_id:
        member_ids = GroupMembership.objects.filter(group_id=group_id).values_list('student_id', flat=True)
        students_qs = students_qs.filter(id__in=member_ids)
    students = list(students_qs.order_by('user__last_name', 'user__first_name'))

    count = len(students)
    grid_rows, grid_cols = _grid_dimensions(count, rows, cols)
    capacity = grid_rows * grid_cols

    student_ids = {s.id for s in students}
    constraints = PeerConstraint.objects.filter(classroom=classroom).filter(
        Q(student_a_id__in=student_ids) & Q(student_b_id__in=student_ids)
    )
    avoid_pairs = {frozenset((c.student_a_id, c.student_b_id)) for c in constraints if c.constraint_type == PeerConstraint.ConstraintType.AVOID}
    prefer_pairs = {frozenset((c.student_a_id, c.student_b_id)) for c in constraints if c.constraint_type == PeerConstraint.ConstraintType.PREFER}

    # Cluster by group membership so groupmates land near each other in the
    # placement order (soft signal, easily overridden by explicit constraints).
    group_of = {}
    if not group_id:
        memberships = GroupMembership.objects.filter(student_id__in=student_ids).select_related('group')
        for m in memberships:
            group_of[m.student_id] = m.group_id

    def placement_order_key(s):
        return (group_of.get(s.id, s.id), s.id)
    ordered_students = sorted(students, key=placement_order_key)

    # PREFER-linked students are placed as a unit right after their partner,
    # so they land in adjacent seats under simple row-major filling.
    placed_ids = set()
    sequence = []
    prefer_partner = {}
    for pair in prefer_pairs:
        a, b = tuple(pair)
        prefer_partner.setdefault(a, b)
        prefer_partner.setdefault(b, a)
    for s in ordered_students:
        if s.id in placed_ids:
            continue
        sequence.append(s)
        placed_ids.add(s.id)
        partner_id = prefer_partner.get(s.id)
        if partner_id and partner_id not in placed_ids:
            partner = next((p for p in ordered_students if p.id == partner_id), None)
            if partner is not None:
                sequence.append(partner)
                placed_ids.add(partner.id)

    positions = [(r, c) for r in range(grid_rows) for c in range(grid_cols)]
    seat_of = {}   # position -> StudentProfile
    student_position = {}  # student_id -> position
    unseated = []
    warnings = []

    def has_avoid_conflict(student_id, pos):
        for npos in _neighbor_positions(pos[0], pos[1], grid_rows, grid_cols):
            neighbor = seat_of.get(npos)
            if neighbor is not None and frozenset((student_id, neighbor.id)) in avoid_pairs:
                return True
        return False

    remaining_positions = list(positions)
    for student in sequence:
        if not remaining_positions:
            unseated.append(student)
            continue
        chosen = None
        # If this student's PREFER partner is already seated, try to land
        # in one of the partner's actual grid neighbors — being next to
        # each other in placement *order* doesn't guarantee grid adjacency
        # (e.g. the last seat of one row and the first seat of the next
        # row are consecutive in row-major order but not adjacent).
        partner_id = prefer_partner.get(student.id)
        if partner_id is not None and partner_id in student_position:
            partner_pos = student_position[partner_id]
            for npos in _neighbor_positions(partner_pos[0], partner_pos[1], grid_rows, grid_cols):
                if npos in remaining_positions and not has_avoid_conflict(student.id, npos):
                    chosen = npos
                    break
        if chosen is None:
            # Prefer the next open row-major seat; fall back to scanning for
            # one that doesn't create an AVOID conflict.
            for pos in remaining_positions:
                if not has_avoid_conflict(student.id, pos):
                    chosen = pos
                    break
        if chosen is None:
            chosen = remaining_positions[0]
            for npos in _neighbor_positions(chosen[0], chosen[1], grid_rows, grid_cols):
                neighbor = seat_of.get(npos)
                if neighbor is not None and frozenset((student.id, neighbor.id)) in avoid_pairs:
                    warnings.append(
                        f'{student.full_name} and {neighbor.full_name} are seated next to each other — '
                        f'the grid was too small to keep them apart.'
                    )
        seat_of[chosen] = student
        student_position[student.id] = chosen
        remaining_positions.remove(chosen)

    seats = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            student = seat_of.get((r, c))
            seats.append({
                'row': r, 'col': c,
                'student': {
                    'id': student.id,
                    'name': student.full_name,
                    'student_id': student.student_id,
                    'group_id': group_of.get(student.id),
                } if student else None,
            })

    return {
        'rows': grid_rows,
        'cols': grid_cols,
        'capacity': capacity,
        'seated_count': len(student_position),
        'seats': seats,
        'unseated': [{'id': s.id, 'name': s.full_name, 'student_id': s.student_id} for s in unseated],
        'warnings': warnings,
    }
