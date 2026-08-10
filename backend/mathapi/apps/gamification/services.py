"""
Streak recalculation and badge evaluation. Both are pure re-derivations
from ExamScore — nothing here holds state that can't be rebuilt from
scratch, so re-running them (e.g. after a score correction) is always safe.
"""
from mathapi.apps.exams.models import ExamScore
from .models import Badge, StudentBadge, StudentStreak


def recalculate_streak(student) -> StudentStreak:
    """
    Recomputes the student's pass streak from every published, non-absent
    score they have, oldest to newest. The *current* streak counts
    consecutive most-recent exams passed — an absence or a fail resets it
    to zero. *Longest* streak is a high-water mark that's never reduced by
    a later reset, but is corrected downward if e.g. a wrongly-entered
    passing score is fixed to a fail (this always recomputes the true
    longest streak from the current data, not accumulated forward).
    """
    scores = list(
        ExamScore.objects.filter(
            student=student, is_absent=False, exam__is_published=True,
        ).select_related('exam').order_by('exam__exam_date', 'exam__created_at', 'id')
    )

    current = 0
    longest = 0
    last_score = None
    for s in scores:
        if s.passed:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
        last_score = s

    streak, _ = StudentStreak.objects.get_or_create(student=student)
    streak.current_streak = current
    streak.longest_streak = longest
    streak.last_exam_id = last_score.exam_id if last_score else None
    streak.last_exam_date = last_score.exam.exam_date if last_score else None
    streak.last_result_passed = last_score.passed if last_score else None
    streak.save()
    return streak


def evaluate_badges(student, streak: StudentStreak, *, triggering_exam=None,
                     is_perfect: bool = False, is_comeback: bool = False) -> list:
    """
    Awards any badges the student newly qualifies for. Returns the newly
    created StudentBadge rows (empty if nothing new). Safe to call
    repeatedly — already-awarded badges are skipped up front, and
    get_or_create makes the actual award idempotent regardless.
    """
    newly_awarded = []
    already_awarded_codes = set(
        StudentBadge.objects.filter(student=student).values_list('badge__code', flat=True)
    )

    total_exams = ExamScore.objects.filter(
        student=student, is_absent=False, exam__is_published=True,
    ).count()

    for badge in Badge.objects.filter(is_active=True).exclude(code__in=already_awarded_codes):
        qualifies = (
            (badge.criteria_type == 'exams_taken' and total_exams >= badge.threshold)
            or (badge.criteria_type == 'streak' and streak.current_streak >= badge.threshold)
            or (badge.criteria_type == 'perfect_score' and is_perfect)
            or (badge.criteria_type == 'comeback' and is_comeback)
        )
        if not qualifies:
            continue
        student_badge, created = StudentBadge.objects.get_or_create(
            student=student, badge=badge, defaults={'exam': triggering_exam},
        )
        if created:
            newly_awarded.append(student_badge)
    return newly_awarded


def process_score_saved(exam_score) -> dict:
    """Entry point called whenever an ExamScore is saved. No-ops for
    unpublished exams or absences — those never count toward progress.
    Returns {'streak': StudentStreak|None, 'new_badges': [StudentBadge]}."""
    if not exam_score.exam.is_published or exam_score.is_absent:
        return {'streak': None, 'new_badges': []}

    student = exam_score.student
    is_perfect = exam_score.percentage >= 100

    previous = (
        ExamScore.objects.filter(student=student, is_absent=False, exam__is_published=True)
        .exclude(id=exam_score.id)
        .filter(exam__exam_date__lt=exam_score.exam.exam_date)
        .select_related('exam')
        .order_by('-exam__exam_date', '-exam__created_at', '-id')
        .first()
    )
    is_comeback = bool(previous) and (not previous.passed) and exam_score.passed

    streak = recalculate_streak(student)
    new_badges = evaluate_badges(
        student, streak, triggering_exam=exam_score.exam,
        is_perfect=is_perfect, is_comeback=is_comeback,
    )
    return {'streak': streak, 'new_badges': new_badges}


def get_student_progress(student) -> dict:
    """Everything a progress widget/page needs for one student: their
    live streak plus every badge they've earned, newest first."""
    streak, _ = StudentStreak.objects.get_or_create(student=student)
    badges = (
        StudentBadge.objects.filter(student=student)
        .select_related('badge', 'exam')
        .order_by('-awarded_at')
    )
    return {'streak': streak, 'badges': list(badges)}
