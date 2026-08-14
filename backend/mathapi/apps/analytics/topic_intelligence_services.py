"""
"Topic Intelligence" — a school/subject-wide view of topic performance,
one level up from the per-student and per-classroom topic views that
already exist (get_student_topic_analysis, get_topic_class_heatmap).

Unifies two data sources into one per-topic timeline:
- exams.models.TopicScore — a topic's sub-score within one exam
- quizzes.models.DailyQuizScore — a whole daily quiz's score, attributed
  to its single tagged topic

Both represent "how did this student do on this topic on this date" and
are combined into one (date, percentage, student_id) series per topic so
trend/distribution/ranking all reflect the full picture, not just exams.
"""
from collections import defaultdict
from mathapi.apps.exams.models import TopicScore, MathTopic


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


def _collect_topic_points(*, subject_id=None, classroom_ids=None, term=None,
                           academic_year=None, created_by_id=None, include_quizzes=True,
                           topic_ids=None):
    """
    Returns {topic_id: [{'date': date, 'pct': float, 'student_id': int,
    'classroom_id': int}, ...]} across both exams and (optionally) quizzes,
    honoring every filter. This is the single shared data-gathering step
    every function below builds its aggregation from, so the two data
    sources are always combined the same way.
    """
    points = defaultdict(list)

    exam_filters = {'exam_score__is_absent': False, 'exam_score__exam__is_published': True}
    if subject_id:
        exam_filters['topic__subject_id'] = subject_id
    if classroom_ids is not None:
        exam_filters['exam_score__student__classroom_id__in'] = classroom_ids
    if term:
        exam_filters['exam_score__exam__term'] = term
    if academic_year:
        exam_filters['exam_score__exam__academic_year'] = academic_year
    if created_by_id:
        exam_filters['exam_score__exam__created_by_id'] = created_by_id
    if topic_ids:
        exam_filters['topic_id__in'] = topic_ids

    topic_scores = TopicScore.objects.filter(**exam_filters).select_related(
        'topic', 'exam_score__exam', 'exam_score__student',
    )
    for ts in topic_scores:
        points[ts.topic_id].append({
            'date': ts.exam_score.exam.exam_date,
            'pct': ts.percentage,
            'student_id': ts.exam_score.student_id,
            'classroom_id': ts.exam_score.student.classroom_id,
        })

    if include_quizzes:
        from mathapi.apps.quizzes.models import DailyQuizScore
        quiz_filters = {'is_absent': False, 'quiz__is_deleted': False, 'quiz__topic__isnull': False}
        if subject_id:
            quiz_filters['quiz__subject_id'] = subject_id
        if classroom_ids is not None:
            quiz_filters['quiz__classroom_id__in'] = classroom_ids
        if term:
            quiz_filters['quiz__term'] = term
        if academic_year:
            quiz_filters['quiz__academic_year'] = academic_year
        if created_by_id:
            quiz_filters['quiz__created_by_id'] = created_by_id
        if topic_ids:
            quiz_filters['quiz__topic_id__in'] = topic_ids

        quiz_scores = DailyQuizScore.objects.filter(**quiz_filters).select_related('quiz', 'quiz__topic')
        for qs in quiz_scores:
            points[qs.quiz.topic_id].append({
                'date': qs.quiz.date,
                'pct': qs.percentage,
                'student_id': qs.student_id,
                'classroom_id': qs.quiz.classroom_id,
            })

    return points


def get_topic_intelligence_overview(*, subject_id=None, classroom_ids=None, term=None,
                                     academic_year=None, created_by_id=None,
                                     include_quizzes=True, changed_limit=5) -> dict:
    """
    The main dashboard payload: every topic's aggregate stats (sorted
    hardest-first), a classroom x topic average matrix, and the topics
    with the strongest positive/negative trend.
    """
    topic_points = _collect_topic_points(
        subject_id=subject_id, classroom_ids=classroom_ids, term=term,
        academic_year=academic_year, created_by_id=created_by_id, include_quizzes=include_quizzes,
    )
    if not topic_points:
        return {'topics': [], 'classroom_matrix': {'classrooms': [], 'topics': [], 'matrix': []},
                'most_improved': [], 'most_declined': []}

    topic_meta = {
        t.id: t for t in MathTopic.objects.filter(id__in=topic_points.keys()).select_related('subject')
    }

    topics_out = []
    for topic_id, pts in topic_points.items():
        topic = topic_meta.get(topic_id)
        if topic is None:
            continue
        pts_sorted = sorted(pts, key=lambda p: p['date'])
        pcts = [p['pct'] for p in pts_sorted]
        student_ids = {p['student_id'] for p in pts_sorted}
        topics_out.append({
            'topic_id': topic_id,
            'topic_name': topic.name,
            'subject_id': topic.subject_id,
            'subject_name': topic.subject.name if topic.subject_id else None,
            'color': topic.color,
            'attempts': len(pcts),
            'student_count': len(student_ids),
            'average': round(sum(pcts) / len(pcts), 1),
            'highest': max(pcts),
            'lowest': min(pcts),
            'trend': _calculate_trend(pcts),
            'trend_slope': _linear_slope(pcts),
        })
    topics_out.sort(key=lambda t: t['average'])  # hardest (lowest average) first
    for i, t in enumerate(topics_out):
        t['difficulty_rank'] = i + 1

    # ── Classroom x topic matrix ─────────────────────────────────────────
    classroom_topic_pcts = defaultdict(lambda: defaultdict(list))
    classroom_ids_seen = set()
    for topic_id, pts in topic_points.items():
        for p in pts:
            if p['classroom_id'] is None:
                continue
            classroom_topic_pcts[p['classroom_id']][topic_id].append(p['pct'])
            classroom_ids_seen.add(p['classroom_id'])

    from mathapi.apps.students.models import Classroom
    classroom_names = dict(Classroom.objects.filter(id__in=classroom_ids_seen).values_list('id', 'name'))
    matrix_topic_ids = [t['topic_id'] for t in topics_out]
    matrix_classroom_ids = sorted(classroom_ids_seen, key=lambda cid: classroom_names.get(cid, ''))

    matrix = []
    for cid in matrix_classroom_ids:
        row = []
        for tid in matrix_topic_ids:
            pcts = classroom_topic_pcts[cid].get(tid, [])
            row.append(round(sum(pcts) / len(pcts), 1) if pcts else None)
        matrix.append(row)

    classroom_matrix = {
        'classrooms': [{'id': cid, 'name': classroom_names.get(cid, f'#{cid}')} for cid in matrix_classroom_ids],
        'topics': [{'id': t['topic_id'], 'name': t['topic_name']} for t in topics_out],
        'matrix': matrix,
    }

    # ── Most improved / declined ─────────────────────────────────────────
    trending = [t for t in topics_out if t['attempts'] >= 2]
    most_improved = sorted(trending, key=lambda t: -t['trend_slope'])[:changed_limit]
    most_improved = [t for t in most_improved if t['trend_slope'] > 0]
    most_declined = sorted(trending, key=lambda t: t['trend_slope'])[:changed_limit]
    most_declined = [t for t in most_declined if t['trend_slope'] < 0]

    return {
        'topics': topics_out,
        'classroom_matrix': classroom_matrix,
        'most_improved': most_improved,
        'most_declined': most_declined,
    }


def get_topic_distribution(topic_id, *, subject_id=None, classroom_ids=None, term=None,
                            academic_year=None, created_by_id=None, include_quizzes=True) -> dict:
    """
    Drill-down for one topic: a mastery histogram (bucketed by each
    student's own average on this topic, not every individual attempt —
    so a student who took 5 quizzes on a topic counts once, not 5 times)
    plus a chronological trend timeline across every attempt.
    """
    topic_points = _collect_topic_points(
        subject_id=subject_id, classroom_ids=classroom_ids, term=term,
        academic_year=academic_year, created_by_id=created_by_id, include_quizzes=include_quizzes,
        topic_ids=[topic_id],
    )
    pts = sorted(topic_points.get(topic_id, []), key=lambda p: p['date'])
    if not pts:
        return {'topic_id': topic_id, 'histogram': [], 'timeline': [], 'summary': None}

    by_student = defaultdict(list)
    for p in pts:
        by_student[p['student_id']].append(p['pct'])
    student_averages = [round(sum(v) / len(v), 1) for v in by_student.values()]

    buckets = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100.01)]
    histogram = []
    for lo, hi in buckets:
        count = sum(1 for a in student_averages if lo <= a < hi)
        histogram.append({'range': f'{lo}-{int(min(hi, 100))}%', 'count': count})

    timeline = [{'date': p['date'].isoformat(), 'percentage': p['pct']} for p in pts]
    all_pcts = [p['pct'] for p in pts]

    summary = {
        'attempts': len(pts),
        'student_count': len(by_student),
        'average': round(sum(all_pcts) / len(all_pcts), 1),
        'highest': max(all_pcts),
        'lowest': min(all_pcts),
        'trend': _calculate_trend(all_pcts),
    }
    return {'topic_id': topic_id, 'histogram': histogram, 'timeline': timeline, 'summary': summary}
