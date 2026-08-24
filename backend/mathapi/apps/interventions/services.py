"""
Slow-learner detection reads a student's ENTIRE exam history (every
published, non-absent ExamScore she has ever sat, not just the current
classroom's recent papers) and looks for a flat-or-falling trend. Program
progress is always re-measured from live ExamScore data — nothing about
"improvement" is stored as a static number a teacher typed in.
"""
from django.db import transaction
from django.utils import timezone

from mathapi.apps.exams.models import ExamScore
from .models import InterventionProgram, InterventionStage, DEFAULT_STAGE_TEMPLATE

MIN_EXAMS_FOR_TREND = 4
FLAT_SLOPE_THRESHOLD = 1.0  # percentage points gained per exam, below this counts as "not improving"


def _history(student, since=None):
    """Chronological (oldest first) list of (exam_date, percentage) across
    every published, non-absent exam this student has ever sat."""
    qs = (
        ExamScore.objects.filter(student=student, is_absent=False, exam__is_published=True)
        .select_related('exam').order_by('exam__exam_date', 'exam__created_at', 'id')
    )
    if since is not None:
        qs = qs.filter(exam__exam_date__gte=since)
    return [(s.exam.exam_date, s.percentage) for s in qs]


def _linear_slope(values):
    """Least-squares slope of percentage vs. exam order index — no numpy
    dependency, just the closed-form formula. Positive = improving."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def current_average(student, since=None):
    history = _history(student, since=since)
    if not history:
        return None
    values = [pct for _, pct in history]
    return round(sum(values) / len(values), 2)


def detect_slow_learners(classroom, min_exams: int = MIN_EXAMS_FOR_TREND,
                          flat_threshold: float = FLAT_SLOPE_THRESHOLD) -> list:
    """
    Scans every active student in `classroom` and flags candidates whose
    lifetime trend line is flat or falling. Students already on an active
    program are excluded (nothing to flag twice). Returns a list of dicts
    ready to render as a review list before a teacher opens a program.
    """
    from mathapi.apps.students.models import StudentProfile

    already_active = set(
        InterventionProgram.objects.filter(
            student__classroom=classroom, status=InterventionProgram.Status.ACTIVE,
        ).values_list('student_id', flat=True)
    )

    candidates = []
    for student in StudentProfile.objects.filter(classroom=classroom, is_active=True):
        if student.id in already_active:
            continue
        history = _history(student)
        if len(history) < min_exams:
            continue
        values = [pct for _, pct in history]
        slope = round(_linear_slope(values), 2)
        if slope > flat_threshold:
            continue
        half = max(1, len(values) // 2)
        early_avg = round(sum(values[:half]) / half, 2)
        recent_avg = round(sum(values[-half:]) / half, 2)
        candidates.append({
            'student': student,
            'exam_count': len(values),
            'slope': slope,
            'early_average': early_avg,
            'recent_average': recent_avg,
            'overall_average': round(sum(values) / len(values), 2),
            'trend': 'falling' if slope < 0 else 'flat',
        })

    candidates.sort(key=lambda c: c['slope'])
    return candidates


@transaction.atomic
def create_program(*, student, classroom, created_by, subject=None,
                    trigger_reason='', custom_stages=None):
    """
    Opens a new program and materializes its stage sequence (default
    5-stage template unless the teacher supplied her own). Stage 1 is
    immediately unlocked (ACTIVE) — every later stage starts PENDING/
    locked until services.start_stage explicitly opens it in order.
    """
    baseline = current_average(student)
    if baseline is None:
        baseline = 0.0

    program = InterventionProgram.objects.create(
        student=student, classroom=classroom, subject=subject, created_by=created_by,
        trigger_reason=trigger_reason, baseline_average=baseline,
    )

    stage_defs = custom_stages if custom_stages else DEFAULT_STAGE_TEMPLATE
    for i, stage_def in enumerate(stage_defs, start=1):
        InterventionStage.objects.create(
            program=program, order=i, title=stage_def['title'],
            description=stage_def.get('description', ''),
            status=InterventionStage.Status.ACTIVE if i == 1 else InterventionStage.Status.PENDING,
            measured_before=baseline if i == 1 else None,
            started_at=timezone.now() if i == 1 else None,
        )
    return program


@transaction.atomic
def start_stage(stage: InterventionStage):
    """Unlocks and starts a stage — refuses unless every earlier stage in
    the same program is COMPLETED or SKIPPED, enforcing the "no stage can
    be reached without completing the previous" rule server-side."""
    earlier = stage.program.stages.filter(order__lt=stage.order).exclude(
        status__in=[InterventionStage.Status.COMPLETED, InterventionStage.Status.SKIPPED],
    )
    if earlier.exists():
        raise ValueError('Complete the earlier stages before starting this one.')
    if stage.status == InterventionStage.Status.ACTIVE:
        return stage
    stage.status = InterventionStage.Status.ACTIVE
    stage.started_at = timezone.now()
    stage.measured_before = current_average(stage.program.student)
    stage.save(update_fields=['status', 'started_at', 'measured_before'])
    return stage


@transaction.atomic
def complete_stage(stage: InterventionStage, notes: str = ''):
    """Marks a stage complete, re-measuring the student's average from
    live exam data since the stage started (falls back to her overall
    average if nothing new has been entered yet). Closing the final stage
    closes the whole program and awards the completion badge."""
    if stage.status != InterventionStage.Status.ACTIVE:
        raise ValueError('Only the currently active stage can be completed.')

    since = stage.started_at.date() if stage.started_at else None
    measured = current_average(stage.program.student, since=since)
    stage.measured_after = measured if measured is not None else current_average(stage.program.student)
    stage.status = InterventionStage.Status.COMPLETED
    stage.completed_at = timezone.now()
    if notes:
        stage.notes = notes
    stage.save(update_fields=['measured_after', 'status', 'completed_at', 'notes'])

    program = stage.program
    remaining = program.stages.exclude(
        status__in=[InterventionStage.Status.COMPLETED, InterventionStage.Status.SKIPPED],
    ).exists()
    if not remaining:
        program.status = InterventionProgram.Status.COMPLETED
        program.completed_at = timezone.now()
        program.latest_average = current_average(program.student)
        program.save(update_fields=['status', 'completed_at', 'latest_average', 'updated_at'])
        _award_intervention_badges(program)
    else:
        program.latest_average = current_average(program.student)
        program.save(update_fields=['latest_average', 'updated_at'])

    return stage


@transaction.atomic
def discontinue_program(program: InterventionProgram, notes: str = ''):
    program.status = InterventionProgram.Status.DISCONTINUED
    program.completed_at = timezone.now()
    program.latest_average = current_average(program.student)
    program.save(update_fields=['status', 'completed_at', 'latest_average', 'updated_at'])
    return program


def _award_intervention_badges(program: InterventionProgram):
    from mathapi.apps.gamification.services import evaluate_badges

    improvement = program.improvement or 0
    return evaluate_badges(
        program.student,
        is_intervention_completed=True,
        is_intervention_turnaround=improvement >= 10,
    )


def get_program_progress(program: InterventionProgram) -> dict:
    """Stage-by-stage before/after data plus overall improvement — the
    payload the interactive stage tracker and its analytics chart read."""
    stages = list(program.stages.order_by('order'))
    return {
        'program_id': program.id,
        'status': program.status,
        'baseline_average': program.baseline_average,
        'latest_average': program.latest_average if program.latest_average is not None else current_average(program.student),
        'improvement': program.improvement,
        'stage_count': len(stages),
        'completed_stage_count': sum(1 for s in stages if s.status == InterventionStage.Status.COMPLETED),
        'stages': [
            {
                'id': s.id, 'order': s.order, 'title': s.title, 'description': s.description,
                'status': s.status, 'measured_before': s.measured_before, 'measured_after': s.measured_after,
                'improvement': s.improvement, 'notes': s.notes,
                'started_at': s.started_at.isoformat() if s.started_at else None,
                'completed_at': s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in stages
        ],
    }


def get_intervention_analytics(classroom=None) -> dict:
    """Dedicated analytics rollup: how many programs are active/completed/
    discontinued, average improvement across completed programs, and a
    per-student improvement leaderboard."""
    qs = InterventionProgram.objects.all()
    if classroom is not None:
        qs = qs.filter(classroom=classroom)

    completed = qs.filter(status=InterventionProgram.Status.COMPLETED)
    improvements = [p.improvement for p in completed if p.improvement is not None]

    return {
        'active_count': qs.filter(status=InterventionProgram.Status.ACTIVE).count(),
        'completed_count': completed.count(),
        'discontinued_count': qs.filter(status=InterventionProgram.Status.DISCONTINUED).count(),
        'average_improvement': round(sum(improvements) / len(improvements), 2) if improvements else None,
        'success_rate': round(
            sum(1 for i in improvements if i > 0) / len(improvements) * 100, 1,
        ) if improvements else None,
        'leaderboard': [
            {
                'student_id': p.student_id, 'student_name': p.student.full_name,
                'improvement': p.improvement, 'baseline_average': p.baseline_average,
                'latest_average': p.latest_average,
            }
            for p in sorted(completed.select_related('student'), key=lambda p: p.improvement or -999, reverse=True)[:15]
        ],
    }
