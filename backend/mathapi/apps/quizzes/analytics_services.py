"""
Analytics for daily quizzes — classroom-level dashboards and per-student
topic-level progress. Deliberately self-contained (small local copies of
the trend/moving-average helpers rather than importing analytics.services)
so this app doesn't take a hard dependency on the analytics app, matching
the pattern already used elsewhere (see accounts.scoping duplicating
Exam.Term rather than importing the exams app at module scope).
"""
from collections import defaultdict
from .models import DailyQuiz, DailyQuizScore


def _linear_slope(values: list) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return round(numerator / denominator, 4) if denominator else 0.0


def _calculate_trend(percentages: list) -> str:
    if len(percentages) < 2:
        return 'stable'
    slope = _linear_slope(percentages)
    if slope > 2:
        return 'improving'
    if slope < -2:
        return 'declining'
    return 'stable'


def _moving_average(values: list, window: int = 3) -> list:
    result = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1):i + 1]
        result.append(round(sum(chunk) / len(chunk), 1))
    return result


def _filtered_quiz_queryset(classroom_id=None, *, subject_id=None, term=None,
                             academic_year=None, topic_id=None, created_by_id=None,
                             student_id=None):
    """Shared filter-building for both classroom and student analytics.
    Always excludes soft-deleted quizzes."""
    qs = DailyQuizScore.objects.filter(quiz__is_deleted=False).select_related('quiz', 'quiz__topic', 'student')
    if classroom_id is not None:
        qs = qs.filter(quiz__classroom_id=classroom_id)
    if student_id is not None:
        qs = qs.filter(student_id=student_id)
    if subject_id:
        qs = qs.filter(quiz__subject_id=subject_id)
    if term:
        qs = qs.filter(quiz__term=term)
    if academic_year:
        qs = qs.filter(quiz__academic_year=academic_year)
    if topic_id:
        qs = qs.filter(quiz__topic_id=topic_id)
    if created_by_id:
        qs = qs.filter(quiz__created_by_id=created_by_id)
    return qs


def get_classroom_quiz_analytics(classroom_id, *, subject_id=None, term=None,
                                  academic_year=None, topic_id=None, created_by_id=None,
                                  at_risk_threshold: float = 50.0) -> dict:
    """
    Full analytics payload for one classroom's daily quizzes:
    - overview: headline numbers
    - trend: daily average/pass-rate series (for a line chart)
    - topic_breakdown: average/attempts/trend per topic (for a bar chart)
    - at_risk_students / top_students: sorted by average quiz %

    `participation_rate` is necessarily an approximation: it compares total
    present scores against (quiz_count × current active roster size), using
    today's roster for every historical quiz. A mid-year transfer in/out
    will shift it slightly for older quizzes — acceptable for a trend
    indicator, called out here so it's never read as an exact figure.
    """
    from mathapi.apps.students.models import StudentProfile

    all_scores_qs = _filtered_quiz_queryset(
        classroom_id, subject_id=subject_id, term=term, academic_year=academic_year,
        topic_id=topic_id, created_by_id=created_by_id,
    )
    all_scores = list(all_scores_qs)
    present = [s for s in all_scores if not s.is_absent]
    absent_count = len(all_scores) - len(present)

    quiz_ids = {s.quiz_id for s in all_scores}
    quiz_count = len(quiz_ids)

    pcts = [s.percentage for s in present]
    average = round(sum(pcts) / len(pcts), 1) if pcts else None
    passed_count = sum(1 for s in present if s.passed)
    pass_rate = round(passed_count / len(present) * 100, 1) if present else None

    active_student_count = StudentProfile.objects.filter(classroom_id=classroom_id, is_active=True).count()
    participation_rate = (
        round(len(present) / (quiz_count * active_student_count) * 100, 1)
        if quiz_count and active_student_count else None
    )

    overview = {
        'quiz_count': quiz_count,
        'scores_entered': len(all_scores),
        'present_count': len(present),
        'absent_count': absent_count,
        'average_score': average,
        'pass_rate': pass_rate,
        'participation_rate': participation_rate,
    }

    # ── Trend: one point per calendar date, averaged across every quiz that day ──
    by_date = defaultdict(list)  # date -> list of DailyQuizScore (present only)
    for s in present:
        by_date[s.quiz.date].append(s)
    trend = []
    for d, day_scores in sorted(by_date.items()):
        day_pcts = [s.percentage for s in day_scores]
        day_passed = sum(1 for s in day_scores if s.passed)
        trend.append({
            'date': d.isoformat(),
            'average': round(sum(day_pcts) / len(day_pcts), 1),
            'pass_rate': round(day_passed / len(day_scores) * 100, 1),
            'quiz_count': len({s.quiz_id for s in day_scores}),
        })

    # ── Topic breakdown ──────────────────────────────────────────────────
    by_topic = defaultdict(list)  # key: (topic_id, topic_name) -> [(date, pct)]
    for s in present:
        topic = s.quiz.topic
        key = (topic.id, topic.name) if topic else (None, 'Mixed / Untagged')
        by_topic[key].append((s.quiz.date, s.percentage))

    topic_breakdown = []
    for (topic_id_key, topic_name), pairs in by_topic.items():
        pairs.sort(key=lambda p: p[0])
        vals = [p[1] for p in pairs]
        topic_breakdown.append({
            'topic_id': topic_id_key,
            'topic_name': topic_name,
            'attempts': len(vals),
            'average': round(sum(vals) / len(vals), 1),
            'highest': max(vals),
            'lowest': min(vals),
            'trend': _calculate_trend(vals),
        })
    topic_breakdown.sort(key=lambda t: t['average'])

    # ── Per-student averages, for at-risk / top lists ───────────────────
    by_student = defaultdict(list)
    student_names = {}
    for s in present:
        by_student[s.student_id].append(s.percentage)
        student_names[s.student_id] = s.student.full_name
    student_averages = [
        {'student_id': sid, 'student_name': student_names[sid],
         'average': round(sum(vals) / len(vals), 1), 'attempts': len(vals)}
        for sid, vals in by_student.items()
    ]
    at_risk_students = sorted(
        [r for r in student_averages if r['average'] < at_risk_threshold],
        key=lambda r: r['average'],
    )[:15]
    top_students = sorted(student_averages, key=lambda r: -r['average'])[:5]

    return {
        'overview': overview,
        'trend': trend,
        'topic_breakdown': topic_breakdown,
        'at_risk_students': at_risk_students,
        'top_students': top_students,
    }


def get_student_quiz_topic_progress(student_id, *, subject_id=None, created_by_id=None) -> dict:
    """
    Per-student quiz analytics: overall summary, a score timeline (for a
    trend chart), and per-topic breakdown (for a topic bar chart) — the
    same shapes the exam-analytics PDF/UI already use, so this can share
    the existing chart-rendering code.
    """
    scores = list(
        _filtered_quiz_queryset(
            student_id=student_id, subject_id=subject_id, created_by_id=created_by_id,
        ).order_by('quiz__date', 'quiz__created_at')
    )
    present = [s for s in scores if not s.is_absent]
    pcts = [s.percentage for s in present]

    timeline = [
        {'exam_date': s.quiz.date.isoformat(), 'percentage': s.percentage,
         'exam_title': s.quiz.display_title, 'exam_id': s.quiz_id}
        for s in present
    ]

    by_topic = defaultdict(list)
    for s in present:
        topic = s.quiz.topic
        key = (topic.id, topic.name) if topic else (None, 'Mixed / Untagged')
        by_topic[key].append(s.percentage)
    topic_data = [
        {
            'topic_id': key[0], 'topic_name': key[1],
            'attempts': len(vals),
            'average': round(sum(vals) / len(vals), 1),
            'highest': max(vals), 'lowest': min(vals),
            'trend': _calculate_trend(vals),
        }
        for key, vals in by_topic.items()
    ]
    topic_data.sort(key=lambda t: -t['average'])

    summary = {
        'quizzes_taken': len(present),
        'quizzes_absent': len(scores) - len(present),
        'average': round(sum(pcts) / len(pcts), 1) if pcts else None,
        'pass_rate': round(sum(1 for s in present if s.passed) / len(present) * 100, 1) if present else None,
        'highest': max(pcts) if pcts else None,
        'lowest': min(pcts) if pcts else None,
        'trend': _calculate_trend(pcts),
        'best_topic': topic_data[0]['topic_name'] if topic_data else None,
        'weakest_topic': topic_data[-1]['topic_name'] if topic_data else None,
    }

    return {
        'summary': summary,
        'timeline': timeline,
        'moving_average': _moving_average(pcts, window=3),
        'topic_data': topic_data,
    }
