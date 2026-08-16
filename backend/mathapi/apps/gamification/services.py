"""
Streak recalculation and badge evaluation. Both are pure re-derivations
from ExamScore/DailyQuizScore — nothing here holds state that can't be
rebuilt from scratch, so re-running them (e.g. after a score correction)
is always safe.

Exam pass-streaks (StudentStreak) and quiz participation-streaks
(QuizStreak) are deliberately separate concepts, tracked separately:
- StudentStreak counts consecutive *exams passed*.
- QuizStreak counts consecutive *quiz occurrences attended* (regardless of
  score) — walking the actual sequence of dates quizzes were given, not
  raw calendar days, so a weekend with no quiz never breaks a streak.
"""
from mathapi.apps.exams.models import ExamScore
from .models import Badge, StudentBadge, StudentStreak, QuizStreak


def recalculate_streak(student) -> StudentStreak:
    """
    Recomputes the student's exam pass streak from every published,
    non-absent score they have, oldest to newest. The *current* streak
    counts consecutive most-recent exams passed — an absence or a fail
    resets it to zero. *Longest* streak is always recomputed from the
    current data (not accumulated forward), so correcting a wrongly
    -entered passing score to a fail will correctly lower it too.
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


def recalculate_quiz_streak(student) -> QuizStreak:
    """
    Recomputes the student's daily-quiz participation streak.

    Groups every (non-deleted) quiz score by the quiz's date, treating a
    date as "attended" if the student has at least one non-absent score
    that date (they may sit multiple quizzes the same day across
    subjects). Walks the *distinct dates quizzes actually happened on*,
    in order — not every calendar day — so the streak isn't broken by
    weekends/holidays with no quiz scheduled. A date with no attended
    score breaks the streak, exactly like a fail breaks the exam streak.
    """
    from mathapi.apps.quizzes.models import DailyQuizScore

    scores = list(
        DailyQuizScore.objects.filter(student=student, quiz__is_deleted=False)
        .select_related('quiz').order_by('quiz__date')
    )

    attended_by_date = {}
    for s in scores:
        d = s.quiz.date
        attended_by_date.setdefault(d, False)
        if not s.is_absent:
            attended_by_date[d] = True

    dates_sorted = sorted(attended_by_date.keys())
    current = 0
    longest = 0
    for d in dates_sorted:
        if attended_by_date[d]:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    streak, _ = QuizStreak.objects.get_or_create(student=student)
    streak.current_streak = current
    streak.longest_streak = longest
    streak.last_quiz_date = dates_sorted[-1] if dates_sorted else None
    streak.save()
    return streak


def evaluate_badges(student, streak: StudentStreak = None, quiz_streak: QuizStreak = None, *,
                     triggering_exam=None, triggering_quiz=None,
                     is_perfect: bool = False, is_comeback: bool = False,
                     is_quiz_perfect: bool = False,
                     tournament_participations: int = None,
                     tournament_match_wins: int = None,
                     tournament_titles: int = None,
                     is_tournament_undefeated: bool = False,
                     is_giant_slayer: bool = False,
                     is_tournament_rising_star: bool = False,
                     is_flawless_duel: bool = False,
                     is_underdog: bool = False) -> list:
    """
    Awards any badges the student newly qualifies for, across both the
    exam-based and quiz-based criteria types. Returns the newly created
    StudentBadge rows (empty if nothing new). Safe to call repeatedly —
    already-awarded badges are skipped up front, and get_or_create makes
    the actual award idempotent regardless.

    Callers only pass the signals relevant to what just happened — e.g.
    process_quiz_score_saved() passes quiz_streak/is_quiz_perfect and
    leaves streak=None, so exam-only badges are simply not re-evaluated
    on a quiz save (they're unaffected by it anyway).
    """
    newly_awarded = []
    already_awarded_codes = set(
        StudentBadge.objects.filter(student=student).values_list('badge__code', flat=True)
    )

    total_exams = None  # computed lazily — only needed for 'exams_taken' badges

    for badge in Badge.objects.filter(is_active=True).exclude(code__in=already_awarded_codes):
        qualifies = False
        if badge.criteria_type == 'exams_taken':
            if total_exams is None:
                total_exams = ExamScore.objects.filter(
                    student=student, is_absent=False, exam__is_published=True,
                ).count()
            qualifies = total_exams >= badge.threshold
        elif badge.criteria_type == 'streak':
            qualifies = streak is not None and streak.current_streak >= badge.threshold
        elif badge.criteria_type == 'perfect_score':
            qualifies = is_perfect
        elif badge.criteria_type == 'comeback':
            qualifies = is_comeback
        elif badge.criteria_type == 'quiz_streak':
            qualifies = quiz_streak is not None and quiz_streak.current_streak >= badge.threshold
        elif badge.criteria_type == 'quiz_perfect':
            qualifies = is_quiz_perfect
        elif badge.criteria_type == 'tournament_participations':
            qualifies = tournament_participations is not None and tournament_participations >= badge.threshold
        elif badge.criteria_type == 'tournament_match_wins':
            qualifies = tournament_match_wins is not None and tournament_match_wins >= badge.threshold
        elif badge.criteria_type == 'tournament_titles':
            qualifies = tournament_titles is not None and tournament_titles >= badge.threshold
        elif badge.criteria_type == 'tournament_undefeated':
            qualifies = is_tournament_undefeated
        elif badge.criteria_type == 'tournament_giant_slayer':
            qualifies = is_giant_slayer
        elif badge.criteria_type == 'tournament_rising_star':
            qualifies = is_tournament_rising_star
        elif badge.criteria_type == 'tournament_flawless_duel':
            qualifies = is_flawless_duel
        elif badge.criteria_type == 'tournament_underdog':
            qualifies = is_underdog

        if not qualifies:
            continue
        student_badge, created = StudentBadge.objects.get_or_create(
            student=student, badge=badge,
            defaults={'exam': triggering_exam, 'quiz': triggering_quiz},
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


def process_quiz_score_saved(quiz_score) -> dict:
    """Entry point called whenever a DailyQuizScore is saved. No-ops for
    soft-deleted quizzes. Absences still recalculate the streak (an
    absence breaks it), they just never count as "attended" or trigger
    the quiz_perfect badge.
    Returns {'streak': QuizStreak|None, 'new_badges': [StudentBadge]}."""
    if quiz_score.quiz.is_deleted:
        return {'streak': None, 'new_badges': []}

    student = quiz_score.student
    is_quiz_perfect = (not quiz_score.is_absent) and quiz_score.percentage >= 100

    quiz_streak = recalculate_quiz_streak(student)
    new_badges = evaluate_badges(
        student, quiz_streak=quiz_streak, triggering_quiz=quiz_score.quiz,
        is_quiz_perfect=is_quiz_perfect,
    )
    return {'streak': quiz_streak, 'new_badges': new_badges}


def get_student_progress(student) -> dict:
    """Everything the exam-progress widget/page needs for one student:
    their live exam pass-streak plus every badge they've earned (across
    both exams and quizzes), newest first."""
    streak, _ = StudentStreak.objects.get_or_create(student=student)
    badges = (
        StudentBadge.objects.filter(student=student)
        .select_related('badge', 'exam')
        .order_by('-awarded_at')
    )
    return {'streak': streak, 'badges': list(badges)}


def get_student_quiz_progress(student) -> dict:
    """Everything the quiz-progress widget/export needs: the live quiz
    participation streak plus only the quiz-related badges (quiz_streak /
    quiz_perfect), newest first."""
    streak, _ = QuizStreak.objects.get_or_create(student=student)
    badges = (
        StudentBadge.objects.filter(student=student, badge__criteria_type__in=['quiz_streak', 'quiz_perfect'])
        .select_related('badge', 'quiz')
        .order_by('-awarded_at')
    )
    return {'streak': streak, 'badges': list(badges)}
