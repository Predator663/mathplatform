"""
All league placement/promotion logic lives here, following the same
"safe to re-run, read scores fresh from ExamScore" philosophy as
tournaments.services and gamification.services.recalculate_streak.
"""
from django.db import transaction
from django.db.models import Max, Count, Avg, Q
from django.utils import timezone

from mathapi.apps.exams.models import ExamScore
from .models import LeagueSeason, LeagueGroup, LeagueMembership, PromotionEvent

DEFAULT_BAND_COLORS = [
    '#94a3b8', '#60a5fa', '#34d399', '#fbbf24', '#f97316',
    '#f43f5e', '#a855f7', '#6366f1', '#14b8a6', '#eab308',
]
DEFAULT_BAND_ICONS = [
    'shield', 'shield-half', 'shield-check', 'sword', 'swords',
    'flame', 'star', 'crown', 'trophy', 'gem',
]


def _percentage(score: ExamScore):
    return score.percentage


def generate_auto_bands(band_width: int = 10):
    """
    Evenly spaced bands covering 0-100%, e.g. width=10 ->
    [(0,9.99), (10,19.99), ... (90,100)]. The top band always closes at
    exactly 100 (rather than 99.99) so a perfect score always has a home.
    Returns a list of dicts ready to become LeagueGroup rows.
    """
    band_width = max(1, min(50, int(band_width or 10)))
    bounds = list(range(0, 100, band_width))
    if bounds[-1] != 100:
        bounds.append(100)
    bands = []
    order = 0
    for i, lo in enumerate(bounds[:-1]):
        hi = bounds[i + 1]
        is_last = (i == len(bounds) - 2)
        top = 100 if is_last else round(hi - 0.01, 2)
        bands.append({
            'name': f'{lo}-{100 if is_last else hi - 1}',
            'min_mark': lo,
            'max_mark': top,
            'order': order,
            'color': DEFAULT_BAND_COLORS[order % len(DEFAULT_BAND_COLORS)],
            'icon': DEFAULT_BAND_ICONS[order % len(DEFAULT_BAND_ICONS)],
        })
        order += 1
    return bands


def _validate_manual_bands(bands):
    """Sorts by min_mark and checks bands don't overlap. Raises ValueError
    with a human-readable message on any problem — never silently drops
    or reorders data the teacher explicitly typed in."""
    if not bands:
        raise ValueError('At least one band is required.')
    cleaned = sorted(
        [{'name': b['name'], 'min_mark': float(b['min_mark']), 'max_mark': float(b['max_mark']),
          'color': b.get('color') or '#6366f1', 'icon': b.get('icon') or 'shield'} for b in bands],
        key=lambda b: b['min_mark'],
    )
    for b in cleaned:
        if b['min_mark'] > b['max_mark']:
            raise ValueError(f"Band \"{b['name']}\" has a minimum above its maximum.")
    for i in range(len(cleaned) - 1):
        if cleaned[i]['max_mark'] >= cleaned[i + 1]['min_mark']:
            raise ValueError(
                f"Bands \"{cleaned[i]['name']}\" and \"{cleaned[i + 1]['name']}\" overlap — "
                f"adjust the intervals so each mark belongs to exactly one band."
            )
    for order, b in enumerate(cleaned):
        b['order'] = order
    return cleaned


@transaction.atomic
def create_season(*, classroom, baseline_exam, title, created_by,
                   interval_mode=LeagueSeason.IntervalMode.AUTO, band_width=10,
                   promotion_mode=LeagueSeason.PromotionMode.MANUAL, manual_bands=None):
    """
    Creates the season, its bands, and places every scored student on the
    baseline exam into the matching band in one transaction. Returns
    (season, unplaced) where `unplaced` is a list of {student, reason}
    for students who couldn't be auto-placed (absent, unscored, or a
    manual band gap) so the teacher can assign them by hand.
    """
    from mathapi.apps.students.models import StudentProfile

    season = LeagueSeason.objects.create(
        title=title, classroom=classroom, baseline_exam=baseline_exam,
        interval_mode=interval_mode, band_width=band_width,
        promotion_mode=promotion_mode, created_by=created_by,
        status=LeagueSeason.Status.ACTIVE, activated_at=timezone.now(),
    )

    if interval_mode == LeagueSeason.IntervalMode.MANUAL:
        bands = _validate_manual_bands(manual_bands or [])
    else:
        bands = generate_auto_bands(band_width)

    groups = [
        LeagueGroup.objects.create(
            season=season, name=b['name'], min_mark=b['min_mark'], max_mark=b['max_mark'],
            order=b['order'], color=b['color'], icon=b['icon'],
        )
        for b in bands
    ]
    groups.sort(key=lambda g: g.order)

    unplaced = []
    students = StudentProfile.objects.filter(classroom=classroom, is_active=True)
    for student in students:
        try:
            exam_score = ExamScore.objects.get(student=student, exam=baseline_exam, is_absent=False)
        except ExamScore.DoesNotExist:
            unplaced.append({'student': student, 'reason': 'No score on the baseline exam (absent or ungraded).'})
            continue
        pct = _percentage(exam_score)
        target = next((g for g in groups if g.contains(pct)), None)
        if target is None:
            unplaced.append({'student': student, 'reason': f'Score {pct}% falls outside every defined band.'})
            continue
        LeagueMembership.objects.create(
            season=season, student=student, group=target,
            placement_score=pct, latest_score=pct, latest_exam=baseline_exam,
        )

    return season, unplaced


@transaction.atomic
def place_student(season: LeagueSeason, student, group: LeagueGroup, score=None):
    """Manual placement/override for a student the auto-placement skipped
    (or a teacher correction). Idempotent — updates an existing membership
    rather than erroring if one already exists."""
    membership, _ = LeagueMembership.objects.update_or_create(
        season=season, student=student,
        defaults={'group': group, 'placement_score': score if score is not None else 0,
                   'latest_score': score, 'is_promotion_pending': False,
                   'pending_target_group': None, 'pending_trigger_score': None},
    )
    return membership


def _best_target_group(season: LeagueSeason, score, groups=None):
    """The highest-order band whose interval contains `score`. Falls back
    to the top band if the score exceeds every defined upper bound (can
    happen with sparse manual bands), so a stellar result is never left
    without a home."""
    groups = list(groups if groups is not None else season.groups.all())
    matches = [g for g in groups if g.contains(score)]
    if matches:
        return max(matches, key=lambda g: g.order)
    above = [g for g in groups if score > float(g.max_mark)]
    if above and len(above) == len(groups):
        return max(groups, key=lambda g: g.order)
    return None


@transaction.atomic
def evaluate_promotions(season: LeagueSeason, trigger_exam):
    """
    The promotion pass: for every active membership in this season, reads
    that student's live score on `trigger_exam` and checks it against her
    CURRENT band's interval. A score above the band's own max stages (or,
    in auto-promotion seasons, immediately applies) a move up to whichever
    band that score actually belongs in — possibly skipping several tiers
    at once for a breakout result. Never relegates: a below-band score
    just leaves the student where she is. Safe to re-run (e.g. after a
    score correction) — already-pending promotions are simply
    recalculated, not duplicated.
    """
    groups = list(season.groups.all())
    memberships = season.memberships.select_related('group', 'student').all()

    evaluated = 0
    staged = 0
    auto_applied = 0
    unchanged = 0
    newly_awarded = {}

    for membership in memberships:
        try:
            exam_score = ExamScore.objects.get(student=membership.student, exam=trigger_exam, is_absent=False)
        except ExamScore.DoesNotExist:
            continue

        pct = _percentage(exam_score)
        evaluated += 1
        membership.latest_score = pct
        membership.latest_exam = trigger_exam

        if pct <= float(membership.group.max_mark):
            membership.is_promotion_pending = False
            membership.pending_target_group = None
            membership.pending_trigger_score = None
            membership.pending_trigger_exam = None
            membership.save(update_fields=[
                'latest_score', 'latest_exam', 'is_promotion_pending',
                'pending_target_group', 'pending_trigger_score', 'pending_trigger_exam', 'updated_at',
            ])
            unchanged += 1
            continue

        target = _best_target_group(season, pct, groups)
        if target is None or target.order <= membership.group.order:
            membership.save(update_fields=['latest_score', 'latest_exam', 'updated_at'])
            unchanged += 1
            continue

        if season.promotion_mode == LeagueSeason.PromotionMode.AUTO:
            PromotionEvent.objects.create(
                membership=membership, season=season, student=membership.student,
                from_group=membership.group, to_group=target, trigger_exam=trigger_exam,
                trigger_score=pct, status=PromotionEvent.Status.AUTO_APPLIED,
                decided_at=timezone.now(),
            )
            membership.group = target
            membership.is_promotion_pending = False
            membership.pending_target_group = None
            membership.pending_trigger_score = None
            membership.pending_trigger_exam = None
            membership.save(update_fields=[
                'latest_score', 'latest_exam', 'group', 'is_promotion_pending',
                'pending_target_group', 'pending_trigger_score', 'pending_trigger_exam', 'updated_at',
            ])
            auto_applied += 1
        else:
            PromotionEvent.objects.get_or_create(
                membership=membership, season=season, student=membership.student,
                from_group=membership.group, to_group=target, trigger_exam=trigger_exam,
                status=PromotionEvent.Status.PENDING,
                defaults={'trigger_score': pct},
            )
            membership.is_promotion_pending = True
            membership.pending_target_group = target
            membership.pending_trigger_score = pct
            membership.pending_trigger_exam = trigger_exam
            membership.save(update_fields=[
                'latest_score', 'latest_exam', 'is_promotion_pending',
                'pending_target_group', 'pending_trigger_score', 'pending_trigger_exam', 'updated_at',
            ])
            staged += 1

        awarded = _award_league_badges(membership.student)
        if awarded:
            newly_awarded[membership.student.id] = [sb.badge for sb in awarded]

    return {
        'evaluated': evaluated, 'staged': staged, 'auto_applied': auto_applied,
        'unchanged': unchanged, 'newly_awarded_badges': newly_awarded,
    }


@transaction.atomic
def apply_promotion(event: PromotionEvent, decided_by=None):
    if event.status != PromotionEvent.Status.PENDING:
        return event
    membership = event.membership
    membership.group = event.to_group
    membership.is_promotion_pending = False
    membership.pending_target_group = None
    membership.pending_trigger_score = None
    membership.pending_trigger_exam = None
    membership.save(update_fields=[
        'group', 'is_promotion_pending', 'pending_target_group',
        'pending_trigger_score', 'pending_trigger_exam', 'updated_at',
    ])
    event.status = PromotionEvent.Status.APPROVED
    event.decided_by = decided_by
    event.decided_at = timezone.now()
    event.save(update_fields=['status', 'decided_by', 'decided_at'])
    _award_league_badges(event.student)
    return event


@transaction.atomic
def reject_promotion(event: PromotionEvent, decided_by=None):
    if event.status != PromotionEvent.Status.PENDING:
        return event
    membership = event.membership
    membership.is_promotion_pending = False
    membership.pending_target_group = None
    membership.pending_trigger_score = None
    membership.pending_trigger_exam = None
    membership.save(update_fields=[
        'is_promotion_pending', 'pending_target_group', 'pending_trigger_score',
        'pending_trigger_exam', 'updated_at',
    ])
    event.status = PromotionEvent.Status.REJECTED
    event.decided_by = decided_by
    event.decided_at = timezone.now()
    event.save(update_fields=['status', 'decided_by', 'decided_at'])
    return event


def _award_league_badges(student):
    from mathapi.apps.gamification.services import evaluate_badges

    promotions_count = PromotionEvent.objects.filter(
        student=student, status__in=[PromotionEvent.Status.APPROVED, PromotionEvent.Status.AUTO_APPLIED],
    ).count()
    is_top_tier = _is_currently_top_tier(student)

    return evaluate_badges(
        student,
        league_promotions=promotions_count,
        is_league_top_tier=is_top_tier,
    )


def _is_currently_top_tier(student):
    for membership in LeagueMembership.objects.filter(student=student).select_related('group', 'season'):
        if membership.is_top_tier:
            return True
    return False


def get_league_analytics(season: LeagueSeason) -> dict:
    """
    Dedicated analytics payload for one season: per-band headcount and
    average, movement summary (staged vs. applied vs. auto), and score
    spread — the "never miss a bit of info" view for a league the way
    tournaments.services.get_tournament_analytics is for a tournament.
    """
    groups = list(season.groups.annotate(
        member_count=Count('members', distinct=True),
    ).order_by('order'))

    band_stats = []
    for g in groups:
        scores = list(
            LeagueMembership.objects.filter(season=season, group=g)
            .exclude(latest_score__isnull=True).values_list('latest_score', flat=True)
        )
        band_stats.append({
            'group_id': g.id, 'name': g.name, 'order': g.order, 'color': g.color, 'icon': g.icon,
            'min_mark': float(g.min_mark), 'max_mark': float(g.max_mark),
            'member_count': g.member_count,
            'average_score': round(sum(scores) / len(scores), 2) if scores else None,
        })

    events = PromotionEvent.objects.filter(season=season)
    pending = list(
        season.memberships.filter(is_promotion_pending=True)
        .select_related('student', 'group', 'pending_target_group')
    )

    total_members = season.memberships.count()
    promoted_ever = events.filter(status__in=[PromotionEvent.Status.APPROVED, PromotionEvent.Status.AUTO_APPLIED]).count()

    return {
        'season_id': season.id,
        'total_members': total_members,
        'band_stats': band_stats,
        'pending_promotions': [
            {
                'membership_id': m.id, 'student_id': m.student_id, 'student_name': m.student.full_name,
                'current_group': m.group.name, 'target_group': m.pending_target_group.name if m.pending_target_group else None,
                'trigger_score': m.pending_trigger_score,
            }
            for m in pending
        ],
        'promotions_staged': events.filter(status=PromotionEvent.Status.PENDING).count(),
        'promotions_applied': promoted_ever,
        'promotions_rejected': events.filter(status=PromotionEvent.Status.REJECTED).count(),
        'promotion_rate': round((promoted_ever / total_members) * 100, 1) if total_members else None,
    }


def get_hall_of_fame(*, classroom=None, limit=10) -> dict:
    """
    School-wide (or classroom-scoped) hall of fame — computed fresh every
    call rather than stored, so it's never stale: current top-tier
    students ranked by their latest score, the students promoted the most
    times ever, and a per-active-season champion list. This is what both
    the Hall of Fame page and its PDF/Excel export read from.
    """
    seasons = LeagueSeason.objects.all()
    if classroom is not None:
        seasons = seasons.filter(classroom=classroom)

    top_tier_rows = []
    champions = []
    for season in seasons.select_related('classroom').prefetch_related('groups'):
        top_order = season.top_group_order
        if top_order is None:
            continue
        top_group = next((g for g in season.groups.all() if g.order == top_order), None)
        if top_group is None:
            continue
        members = (
            LeagueMembership.objects.filter(season=season, group=top_group)
            .exclude(latest_score__isnull=True)
            .select_related('student', 'group')
            .order_by('-latest_score')
        )
        for m in members:
            top_tier_rows.append({
                'student_id': m.student_id, 'student_name': m.student.full_name,
                'classroom': str(season.classroom), 'season_title': season.title,
                'group_name': m.group.name, 'score': m.latest_score,
            })
        top_scorer = members.first()
        if top_scorer:
            champions.append({
                'season_id': season.id, 'season_title': season.title, 'classroom': str(season.classroom),
                'student_id': top_scorer.student_id, 'student_name': top_scorer.student.full_name,
                'group_name': top_group.name, 'score': top_scorer.latest_score,
            })

    top_tier_rows.sort(key=lambda r: r['score'] or 0, reverse=True)

    promotion_qs = PromotionEvent.objects.filter(
        status__in=[PromotionEvent.Status.APPROVED, PromotionEvent.Status.AUTO_APPLIED],
    )
    if classroom is not None:
        promotion_qs = promotion_qs.filter(season__classroom=classroom)
    most_promoted = (
        promotion_qs.values('student_id', 'student__user__first_name', 'student__user__last_name')
        .annotate(promotion_count=Count('id'))
        .order_by('-promotion_count')[:limit]
    )
    most_promoted_rows = [
        {
            'student_id': row['student_id'],
            'student_name': f"{row['student__user__first_name']} {row['student__user__last_name']}".strip(),
            'promotion_count': row['promotion_count'],
        }
        for row in most_promoted
    ]

    return {
        'top_tier': top_tier_rows[:limit],
        'season_champions': champions,
        'most_promoted': most_promoted_rows,
        'generated_at': timezone.now().isoformat(),
    }


def get_student_league_summary(student) -> dict:
    """Lightweight per-student read used by report engines (PDF/analytics)
    to show current league standing and promotion badge state alongside
    exam/tournament/badge data."""
    memberships = (
        LeagueMembership.objects.filter(student=student)
        .select_related('group', 'season', 'pending_target_group')
        .order_by('-season__created_at')
    )
    promotions = PromotionEvent.objects.filter(
        student=student, status__in=[PromotionEvent.Status.APPROVED, PromotionEvent.Status.AUTO_APPLIED],
    ).count()
    return {
        'memberships': [
            {
                'season_id': m.season_id, 'season_title': m.season.title,
                'group_name': m.group.name, 'group_color': m.group.color, 'is_top_tier': m.is_top_tier,
                'latest_score': m.latest_score,
                'is_promotion_pending': m.is_promotion_pending,
                'pending_target_group': m.pending_target_group.name if m.pending_target_group else None,
            }
            for m in memberships
        ],
        'lifetime_promotions': promotions,
    }
