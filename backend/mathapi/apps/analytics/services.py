"""
Analytics computation services — subject-aware.
All heavy data processing lives here; views stay thin.
"""
from django.db.models import Q
from collections import defaultdict
from mathapi.apps.exams.models import ExamScore, TopicScore, Exam, ExamTopicWeight, ScoreEditLog
from mathapi.apps.students.models import StudentProfile, Classroom


# ── Student analytics ────────────────────────────────────────────────────────

def get_student_summary(student_id: int, subject_id: int = None, created_by_id: int = None) -> dict:
    try:
        student = StudentProfile.objects.select_related('user', 'classroom').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return {}

    filters = Q(student=student, is_absent=False)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if created_by_id:
        # A teacher viewing a student's summary should only see exams they
        # personally created, matching scope_exams()'s isolation rule —
        # otherwise a teacher assigned to this student's classroom for any
        # subject sees every other teacher's exam data for that student too.
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('exam').order_by('exam__exam_date')

    if not scores.exists():
        # Always return the full shape the frontend expects (recent_scores,
        # pass_rate, highest/lowest_percentage, etc). Previously this returned
        # a sparse dict missing those keys, which crashed the React page with
        # an uncaught "Cannot read properties of undefined (reading 'map')"
        # on summary.recent_scores — with no error boundary in the app, that
        # uncaught error rendered as a blank page instead of an empty state.
        return {
            'student_id': student_id,
            'student_name': student.full_name,
            'student_code': student.student_id,
            'classroom': str(student.classroom) if student.classroom else None,
            'total_exams': 0,
            'average_percentage': None,
            'highest_percentage': 0,
            'lowest_percentage': 0,
            'pass_rate': 0,
            'trend': 'no_data',
            'predicted_necta_grade': None,
            'recent_scores': [],
        }

    percentages = [s.percentage for s in scores]
    passed = [s for s in scores if s.passed]
    predicted_grade = _predict_necta_grade(percentages)

    return {
        'student_id': student_id,
        'student_name': student.full_name,
        'student_code': student.student_id,
        'classroom': str(student.classroom) if student.classroom else None,
        'total_exams': len(percentages),
        'average_percentage': round(sum(percentages) / len(percentages), 1),
        'highest_percentage': max(percentages),
        'lowest_percentage': min(percentages),
        'pass_rate': round((len(passed) / len(percentages)) * 100, 1),
        'trend': _calculate_trend(percentages),
        'predicted_necta_grade': predicted_grade,
        'recent_scores': [
            {
                'exam_id': s.exam.id,
                'exam_title': s.exam.title,
                'exam_type': s.exam.exam_type,
                'exam_date': str(s.exam.exam_date),
                'score': float(s.score),
                'max_score': float(s.exam.max_score),
                'percentage': s.percentage,
                'letter_grade': s.letter_grade,
                'passed': s.passed,
            }
            for s in scores.order_by('-exam__exam_date')[:5]
        ],
    }


def get_student_trend(
    student_id: int,
    exam_type: str = None,
    term: str = None,
    subject_id: int = None,
    created_by_id: int = None,
) -> dict:
    filters = Q(student_id=student_id, is_absent=False)
    if exam_type:
        filters &= Q(exam__exam_type=exam_type)
    if term:
        filters &= Q(exam__term=term)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('exam').order_by('exam__exam_date')

    timeline = [
        {
            'exam_id': s.exam.id,
            'exam_title': s.exam.title,
            'exam_type': s.exam.exam_type,
            'term': s.exam.term,
            'academic_year': s.exam.academic_year,
            'exam_date': str(s.exam.exam_date),
            'score': float(s.score),
            'max_score': float(s.exam.max_score),
            'percentage': s.percentage,
            'letter_grade': s.letter_grade,
            'passed': s.passed,
        }
        for s in scores
    ]
    percentages = [t['percentage'] for t in timeline]

    return {
        'student_id': student_id,
        'timeline': timeline,
        'trend': _calculate_trend(percentages),
        'trend_slope': _linear_slope(percentages),
        'moving_average': _moving_average(percentages, window=3),
    }


def get_student_topic_analysis(student_id: int, subject_id: int = None, created_by_id: int = None) -> dict:
    filters = Q(exam_score__student_id=student_id, exam_score__is_absent=False)
    if subject_id:
        filters &= Q(topic__subject_id=subject_id)
    if created_by_id:
        filters &= Q(exam_score__exam__created_by_id=created_by_id)

    topic_scores = TopicScore.objects.filter(filters).select_related(
        'topic', 'exam_score__exam'
    ).order_by('exam_score__exam__exam_date')

    topic_data = defaultdict(lambda: {'scores': [], 'topic_name': '', 'color': ''})

    for ts in topic_scores:
        key = ts.topic_id
        topic_data[key]['topic_id'] = ts.topic_id
        topic_data[key]['topic_name'] = ts.topic.name
        topic_data[key]['color'] = ts.topic.color
        topic_data[key]['scores'].append({
            'percentage': ts.percentage,
            'exam_date': str(ts.exam_score.exam.exam_date),
            'exam_title': ts.exam_score.exam.title,
        })

    result = []
    for topic_id, data in topic_data.items():
        pcts = [s['percentage'] for s in data['scores']]
        result.append({
            'topic_id': topic_id,
            'topic_name': data['topic_name'],
            'color': data['color'],
            'average': round(sum(pcts) / len(pcts), 1),
            'highest': max(pcts),
            'lowest': min(pcts),
            'attempts': len(pcts),
            'trend': _calculate_trend(pcts),
            'history': data['scores'],
        })

    result.sort(key=lambda x: x['average'])
    return {'student_id': student_id, 'topics': result}


# ── Class analytics ──────────────────────────────────────────────────────────

def get_student_classroom_comparison(student_id: int, subject_id: int = None, created_by_id: int = None) -> dict:
    """
    For a student's report: how they compare to their classmates.

    Returns, per exam the student took, the classroom average on that same
    exam (so a trend chart can show "you" vs "class" side by side), plus the
    student's rank and percentile within the classroom based on overall
    average across the same scoped set of exams/scores. classroom average is
    computed by pooling ALL classroom scores (including the student's own —
    same convention as the rest of the app's classroom averages), not just
    classmates, so it lines up with the "class average" figure shown
    elsewhere (e.g. the classroom analytics page).
    """
    try:
        student = StudentProfile.objects.select_related('classroom').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return {'by_exam': {}, 'rank': None, 'class_size': 0, 'percentile': None}

    if not student.classroom_id:
        return {'by_exam': {}, 'rank': None, 'class_size': 0, 'percentile': None}

    filters = Q(student__classroom_id=student.classroom_id, is_absent=False)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    rows = ExamScore.objects.filter(filters).values_list('exam_id', 'student_id', 'score', 'exam__max_score')

    by_exam_pcts = defaultdict(list)
    by_student_pcts = defaultdict(list)
    for exam_id, sid, score, max_score in rows:
        if not max_score:
            continue
        pct = round((float(score) / float(max_score)) * 100, 1)
        by_exam_pcts[exam_id].append(pct)
        by_student_pcts[sid].append(pct)

    by_exam_avg = {
        exam_id: round(sum(pcts) / len(pcts), 1)
        for exam_id, pcts in by_exam_pcts.items()
    }

    student_overall_avgs = {
        sid: round(sum(pcts) / len(pcts), 1)
        for sid, pcts in by_student_pcts.items() if pcts
    }
    class_size = len(student_overall_avgs)
    rank, percentile = None, None
    if student_id in student_overall_avgs and class_size > 0:
        ranked = sorted(student_overall_avgs.values(), reverse=True)
        my_avg = student_overall_avgs[student_id]
        rank = ranked.index(my_avg) + 1
        percentile = round(100 * (class_size - rank) / max(class_size - 1, 1), 1) if class_size > 1 else 100.0

    return {
        'by_exam': by_exam_avg,
        'rank': rank,
        'class_size': class_size,
        'percentile': percentile,
    }


def get_class_analytics(
    classroom_id: int,
    academic_year: str = None,
    term: str = None,
    subject_id: int = None,
    created_by_id: int = None,
    stream_id: int = None,
) -> dict:
    try:
        classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
    except Classroom.DoesNotExist:
        return {}

    filters = Q(student__classroom_id=classroom_id, is_absent=False)
    exam_filters = Q(classrooms=classroom, is_deleted=False)
    if academic_year:
        filters &= Q(exam__academic_year=academic_year)
        exam_filters &= Q(academic_year=academic_year)
    if term:
        filters &= Q(exam__term=term)
        exam_filters &= Q(term=term)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
        exam_filters &= Q(subject_id=subject_id)
    if stream_id:
        filters &= Q(student__stream_id=stream_id)
    if created_by_id:
        # Restricts this classroom's analytics to exams the requesting
        # teacher actually created — without this, a teacher with any
        # TeacherAssignment in this classroom (for any subject) saw every
        # other teacher's exam data here too, contradicting the isolation
        # scope_exams() enforces everywhere else.
        filters &= Q(exam__created_by_id=created_by_id)
        exam_filters &= Q(created_by_id=created_by_id)

    exams = Exam.objects.filter(exam_filters).order_by('exam_date')
    exam_summaries = []
    weak_topics = []

    for exam in exams:
        exam_scores = ExamScore.objects.filter(exam=exam, student__classroom_id=classroom_id, is_absent=False)
        if stream_id:
            exam_scores = exam_scores.filter(student__stream_id=stream_id)
        if not exam_scores.exists():
            continue
        pcts = [s.percentage for s in exam_scores]
        passed = [s for s in exam_scores if s.passed]
        exam_summaries.append({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'exam_type': exam.exam_type,
            'term': exam.term,
            'exam_date': str(exam.exam_date),
            'subject': exam.subject.name if exam.subject_id else None,
            'student_count': len(pcts),
            'average': round(sum(pcts) / len(pcts), 1),
            'highest': round(max(pcts), 1),
            'lowest': round(min(pcts), 1),
            'pass_rate': round((len(passed) / len(pcts)) * 100, 1),
            'std_dev': round(_std_dev(pcts), 1),
        })

    # Compute weak topics (class average < 40%)
    from mathapi.apps.exams.models import ExamTopicWeight
    topic_avgs = defaultdict(list)
    for tw in ExamTopicWeight.objects.filter(exam__in=exams).select_related('topic'):
        ts_qs = TopicScore.objects.filter(
            exam_score__exam=tw.exam,
            exam_score__student__classroom_id=classroom_id,
            exam_score__is_absent=False,
            topic=tw.topic,
        )
        if stream_id:
            ts_qs = ts_qs.filter(exam_score__student__stream_id=stream_id)
        if ts_qs.exists():
            avg = sum(ts.percentage for ts in ts_qs) / ts_qs.count()
            topic_avgs[tw.topic].append(avg)

    for topic, avgs in topic_avgs.items():
        class_avg = sum(avgs) / len(avgs)
        if class_avg < 40:
            weak_topics.append({
                'topic': topic.name,
                'avg': round(class_avg, 1),
                'subject': topic.subject.name if topic.subject_id else None,
            })

    all_scores = ExamScore.objects.filter(filters)
    all_pcts = [s.percentage for s in all_scores]

    student_avgs = defaultdict(list)
    for s in all_scores:
        student_avgs[s.student_id].append(s.percentage)

    # Batch-fetch all student profiles needed for rankings in a single query
    # instead of calling .get(id=sid) once per student inside the loop.
    profile_map = {
        sp.id: sp
        for sp in StudentProfile.objects.select_related('user').filter(
            id__in=list(student_avgs.keys())
        )
    }

    rankings = []
    for sid, pcts_list in student_avgs.items():
        sp = profile_map.get(sid)
        if not sp:
            continue
        rankings.append({
            'student_id': sid,
            'student_name': sp.full_name,
            'student_code': sp.student_id,
            'average': round(sum(pcts_list) / len(pcts_list), 1),
            'exams_taken': len(pcts_list),
        })

    rankings.sort(key=lambda x: x['average'], reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1

    # ── At-risk students ─────────────────────────────────────────────────
    # Uses get_at_risk_students() — the same recent-3-exam-average < 30%
    # (or declining) rule as the Dashboard tile and the dedicated At-Risk
    # page — instead of the "overall average across every exam < 50%" rule
    # this used to apply. That older rule used a different threshold, a
    # different window (all-time vs. recent), and no declining check, so
    # the same student could show up as "at risk" here but not on the
    # At-Risk page, or vice versa. Field names are kept matching `rankings`
    # (student_id, student_name, exams_taken, average) so the frontend,
    # which was built against that shape, doesn't need to change.
    exams_taken_map = {r['student_id']: r['exams_taken'] for r in rankings}
    at_risk_raw = get_at_risk_students(
        classroom_ids=classroom_id,
        threshold=30.0,
        subject_id=subject_id,
        created_by_id=created_by_id,
        stream_id=stream_id,
    )
    at_risk_students = [
        {
            'student_id': r['student_id'],
            'student_name': r['student_name'],
            'exams_taken': exams_taken_map.get(r['student_id'], len(r['recent_scores'])),
            'average': r['recent_average'],
            'declining': r['flags']['declining'],
        }
        for r in at_risk_raw
    ]

    return {
        'classroom_id': classroom_id,
        'classroom_name': str(classroom),
        'grade_level': classroom.grade_level.name,
        'exam_summaries': exam_summaries,
        'overall_average': round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else None,
        'student_rankings': rankings,
        'at_risk_students': at_risk_students,
        'top_performers': rankings[:5],
        'distribution': _score_distribution(all_pcts),
        'weak_topics': weak_topics,
        'weak_topic_count': len(weak_topics),
    }


def get_topic_class_heatmap(
    classroom_id: int,
    academic_year: str = None,
    subject_id: int = None,
    created_by_id: int = None,
    stream_id: int = None,
) -> dict:
    filters = Q(
        exam_score__student__classroom_id=classroom_id,
        exam_score__is_absent=False,
    )
    if academic_year:
        filters &= Q(exam_score__exam__academic_year=academic_year)
    if subject_id:
        filters &= Q(topic__subject_id=subject_id)
    if stream_id:
        filters &= Q(exam_score__student__stream_id=stream_id)
    if created_by_id:
        filters &= Q(exam_score__exam__created_by_id=created_by_id)

    topic_scores = TopicScore.objects.filter(filters).select_related(
        'topic', 'exam_score__student__user'
    )

    matrix = defaultdict(lambda: defaultdict(list))
    topics = {}
    students = {}

    for ts in topic_scores:
        sid = ts.exam_score.student_id
        tid = ts.topic_id
        matrix[sid][tid].append(ts.percentage)
        topics[tid] = {'id': tid, 'name': ts.topic.name, 'color': ts.topic.color}
        students[sid] = {
            'id': sid,
            'name': ts.exam_score.student.full_name,
            'code': ts.exam_score.student.student_id,
        }

    heatmap_rows = []
    for sid, student_info in students.items():
        row = {'student': student_info, 'topics': {}}
        for tid in topics:
            pcts = matrix[sid].get(tid, [])
            row['topics'][tid] = round(sum(pcts) / len(pcts), 1) if pcts else None
        heatmap_rows.append(row)

    return {'classroom_id': classroom_id, 'topics': list(topics.values()), 'rows': heatmap_rows}


def get_at_risk_students(
    classroom_ids=None,
    threshold: float = 50.0,
    subject_id: int = None,
    created_by_id: int = None,
    stream_id: int = None,
    trend: str = None,
) -> list:
    """
    trend: optional filter on the recent trajectory of an already-flagged
    at-risk student — 'declining' | 'stable' | 'improving'. Trajectory is
    the same up-to-3-most-recent-exam window used for the 'declining' flag
    (newest vs. oldest of that window, ±10 percentage points): a delta of
    -10 or worse is 'declining', +10 or better is 'improving', anything in
    between (including students with fewer than 2 recent scores, where no
    direction can be read) is 'stable'. This never changes *who* counts as
    at-risk (still avg < threshold OR declining) — it only lets a caller
    narrow the flagged cohort down to, say, the ones who are already
    trending the right way despite still being below threshold, versus
    the ones getting worse.
    """
    filters = Q(is_absent=False)
    if classroom_ids:
        if isinstance(classroom_ids, int):
            filters &= Q(student__classroom_id=classroom_ids)
        else:
            filters &= Q(student__classroom_id__in=classroom_ids)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if stream_id:
        filters &= Q(student__stream_id=stream_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related(
        'student__user', 'exam'
    ).order_by('student_id', '-exam__exam_date')

    student_recent = defaultdict(list)
    for s in scores:
        if len(student_recent[s.student_id]) < 3:
            student_recent[s.student_id].append(s.percentage)

    # Batch-fetch all student profiles needed in a single query.
    at_risk_sids = [
        sid for sid, recent_pcts in student_recent.items()
        if recent_pcts and (
            sum(recent_pcts) / len(recent_pcts) < threshold
            or (len(recent_pcts) >= 2 and recent_pcts[0] < recent_pcts[-1] - 10)
        )
    ]
    profile_map = {
        sp.id: sp
        for sp in StudentProfile.objects.select_related('user', 'classroom').filter(
            id__in=at_risk_sids
        )
    }

    at_risk = []
    for sid in at_risk_sids:
        recent_pcts = student_recent[sid]
        avg = sum(recent_pcts) / len(recent_pcts)
        declining = len(recent_pcts) >= 2 and recent_pcts[0] < recent_pcts[-1] - 10
        sp = profile_map.get(sid)
        if not sp:
            continue

        if len(recent_pcts) < 2:
            trend_value = 'stable'
        else:
            delta = recent_pcts[0] - recent_pcts[-1]
            if delta <= -10:
                trend_value = 'declining'
            elif delta >= 10:
                trend_value = 'improving'
            else:
                trend_value = 'stable'

        if trend and trend_value != trend:
            continue

        at_risk.append({
            'student_id': sid,
            'student_name': sp.full_name,
            'student_code': sp.student_id,
            'classroom': str(sp.classroom) if sp.classroom else None,
            'recent_average': round(avg, 1),
            'recent_scores': recent_pcts,
            'trend': trend_value,
            'flags': {
                'below_threshold': avg < threshold,
                'declining': declining,
            },
        })

    at_risk.sort(key=lambda x: x['recent_average'])
    return at_risk


def get_most_improved_students(
    classroom_ids=None,
    subject_id: int = None,
    created_by_id: int = None,
    stream_id: int = None,
    min_exams: int = 2,
    limit: int = None,
) -> list:
    """Ranks students by growth (first exam % -> most recent exam %), not
    raw average — so a student climbing from 38% to 62% outranks one who
    was always at 85%. Mirrors get_at_risk_students' query shape so the two
    stay easy to compare/maintain side by side.

    Growth here spans *all* of a student's exams in scope (oldest to
    newest), unlike comparison_services._growth which only looks at a
    manually-picked pair of students — this is a whole-classroom ranking.
    """
    filters = Q(is_absent=False)
    if classroom_ids:
        if isinstance(classroom_ids, int):
            filters &= Q(student__classroom_id=classroom_ids)
        else:
            filters &= Q(student__classroom_id__in=classroom_ids)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if stream_id:
        filters &= Q(student__stream_id=stream_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related(
        'student__user', 'exam'
    ).order_by('student_id', 'exam__exam_date')

    student_pcts = defaultdict(list)
    for s in scores:
        student_pcts[s.student_id].append(s.percentage)

    eligible_sids = [sid for sid, pcts in student_pcts.items() if len(pcts) >= min_exams]
    profile_map = {
        sp.id: sp
        for sp in StudentProfile.objects.select_related('user', 'classroom').filter(
            id__in=eligible_sids
        )
    }

    improved = []
    for sid in eligible_sids:
        sp = profile_map.get(sid)
        if not sp:
            continue
        pcts = student_pcts[sid]
        first_pct, last_pct = pcts[0], pcts[-1]
        improved.append({
            'student_id': sid,
            'student_name': sp.full_name,
            'student_code': sp.student_id,
            'classroom': str(sp.classroom) if sp.classroom else None,
            'first_percentage': first_pct,
            'latest_percentage': last_pct,
            'delta': round(last_pct - first_pct, 1),
            'exams_counted': len(pcts),
        })

    improved.sort(key=lambda x: x['delta'], reverse=True)
    if limit:
        improved = improved[:limit]
    return improved


def get_classroom_trend_roster(
    classroom_id: int,
    subject_id: int = None,
    created_by_id: int = None,
    stream_id: int = None,
    min_exams: int = 2,
) -> dict:
    """
    Classifies every student in a classroom as 'improving', 'declining', or
    'stable' from their exam score trend line (same slope math and >2/<-2
    thresholds as _calculate_trend, so this stays consistent with every
    other trend label already shown on a student's own report).

    Unlike get_most_improved_students (which ranks by raw first->last
    delta and is meant for a "who grew the most" leaderboard), this
    returns the FULL roster classified into three buckets — the "who's
    rising, who's dropping, who's stable" view of a whole class at once.
    Students with fewer than `min_exams` scores are grouped separately as
    'insufficient_data' rather than silently guessed at.
    """
    filters = Q(is_absent=False, student__classroom_id=classroom_id)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if stream_id:
        filters &= Q(student__stream_id=stream_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('student__user').order_by(
        'student_id', 'exam__exam_date',
    )

    student_pcts = defaultdict(list)
    for s in scores:
        student_pcts[s.student_id].append(s.percentage)

    profile_map = {
        sp.id: sp
        for sp in StudentProfile.objects.select_related('user').filter(id__in=list(student_pcts.keys()))
    }

    roster = []
    insufficient = []
    for sid, pcts in student_pcts.items():
        sp = profile_map.get(sid)
        if not sp:
            continue
        row = {
            'student_id': sid,
            'student_name': sp.full_name,
            'student_code': sp.student_id,
            'exams_counted': len(pcts),
            'first_percentage': pcts[0],
            'latest_percentage': pcts[-1],
            'delta': round(pcts[-1] - pcts[0], 1),
            'slope': _linear_slope(pcts),
        }
        if len(pcts) < min_exams:
            insufficient.append(row)
        else:
            row['trend'] = _calculate_trend(pcts)
            roster.append(row)

    roster.sort(key=lambda r: r['slope'], reverse=True)
    improving = [r for r in roster if r['trend'] == 'improving']
    declining = [r for r in roster if r['trend'] == 'declining']
    stable = [r for r in roster if r['trend'] == 'stable']

    return {
        'classroom_id': classroom_id,
        'improving': improving,
        'declining': declining,
        'stable': stable,
        'insufficient_data': insufficient,
        'summary': {
            'improving_count': len(improving),
            'declining_count': len(declining),
            'stable_count': len(stable),
            'insufficient_data_count': len(insufficient),
        },
    }


def get_comparative_analysis(
    classroom_ids: list,
    academic_year: str = None,
    term: str = None,
    subject_id: int = None,
    created_by_id: int = None,
) -> dict:
    results = []
    for cid in classroom_ids:
        data = get_class_analytics(
            cid, academic_year=academic_year, term=term,
            subject_id=subject_id, created_by_id=created_by_id,
        )
        if data:
            results.append({
                'classroom_id': cid,
                'classroom_name': data.get('classroom_name'),
                'overall_average': data.get('overall_average'),
                'exam_summaries': data.get('exam_summaries', []),
            })
    return {'comparisons': results}


def get_stream_comparison(
    classroom_id: int,
    academic_year: str = None,
    term: str = None,
    subject_id: int = None,
    created_by_id: int = None,
) -> dict:
    """
    Side-by-side stream comparison within ONE classroom (e.g. Form 2 "A" vs
    "B" vs "C") — one call instead of running get_class_analytics once per
    stream and diffing manually. Students with no stream assigned are
    grouped under a 'No stream' bucket rather than dropped, so the totals
    still reconcile with the classroom-wide average.

    at_risk_count reuses get_at_risk_students()'s standard rule (recent-3
    average < 30% or a >10pt decline) for consistency with the At-Risk page
    and get_class_analytics's own at-risk figure.
    """
    from mathapi.apps.students.models import Stream

    try:
        classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
    except Classroom.DoesNotExist:
        return {}

    filters = Q(student__classroom_id=classroom_id, is_absent=False)
    if academic_year:
        filters &= Q(exam__academic_year=academic_year)
    if term:
        filters &= Q(exam__term=term)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('student')
    stream_names = {s.id: s.name for s in Stream.objects.filter(classroom_id=classroom_id)}

    by_stream_scores = defaultdict(list)   # stream_id (or None) -> [ExamScore]
    by_stream_students = defaultdict(set)
    for s in scores:
        key = s.student.stream_id
        by_stream_scores[key].append(s)
        by_stream_students[key].add(s.student_id)

    # At-risk counts per stream, computed once for the whole classroom then
    # bucketed by each student's stream — cheaper than one call per stream.
    at_risk_raw = get_at_risk_students(
        classroom_ids=classroom_id, threshold=30.0,
        subject_id=subject_id, created_by_id=created_by_id,
    )
    at_risk_student_ids = [r['student_id'] for r in at_risk_raw]
    stream_by_student = {
        sp.id: sp.stream_id
        for sp in StudentProfile.objects.filter(id__in=at_risk_student_ids)
    }
    at_risk_by_stream = defaultdict(int)
    for sid in at_risk_student_ids:
        at_risk_by_stream[stream_by_student.get(sid)] += 1

    rows = []
    for stream_id, score_list in by_stream_scores.items():
        pcts = [sc.percentage for sc in score_list]
        passed = [sc for sc in score_list if sc.passed]
        rows.append({
            'stream_id': stream_id,
            'stream_name': stream_names.get(stream_id, 'No stream'),
            'student_count': len(by_stream_students[stream_id]),
            'exams_recorded': len(pcts),
            'average': round(sum(pcts) / len(pcts), 1) if pcts else None,
            'pass_rate': round((len(passed) / len(pcts)) * 100, 1) if pcts else None,
            'highest': round(max(pcts), 1) if pcts else None,
            'lowest': round(min(pcts), 1) if pcts else None,
            'std_dev': round(_std_dev(pcts), 1) if pcts else None,
            'at_risk_count': at_risk_by_stream.get(stream_id, 0),
        })

    # Streams with no scores yet (e.g. brand new stream) still appear, at
    # zero, so a teacher can see every stream exists rather than only the
    # ones with data so far.
    covered = {r['stream_id'] for r in rows}
    for sid, name in stream_names.items():
        if sid not in covered:
            rows.append({
                'stream_id': sid, 'stream_name': name, 'student_count': 0, 'exams_recorded': 0,
                'average': None, 'pass_rate': None, 'highest': None, 'lowest': None,
                'std_dev': None, 'at_risk_count': 0,
            })

    rows.sort(key=lambda r: (r['average'] is None, -(r['average'] or 0)))

    return {
        'classroom_id': classroom_id,
        'classroom_name': str(classroom),
        'streams': rows,
    }


# ── Intelligence layer ────────────────────────────────────────────────────────
# Five deeper analytics features built on the same scoping conventions as the
# rest of this module (subject_id / created_by_id passthrough for teacher
# isolation). Each is read-only and computed on demand — no new models.


def get_integrity_flags(
    classroom_ids=None,
    subject_id: int = None,
    created_by_id: int = None,
    min_edit_delta: float = 15.0,
    stream_id: int = None,
) -> dict:
    """
    Feature 1 — Grade Integrity / Anomaly Detection.

    Mines ScoreEditLog (previously write-only — created on every score edit
    but never analyzed) for patterns that look like manipulation rather than
    honest correction:

      - boundary_crossings: an edit that moved a score from failing to
        passing (relative to that exam's passing_score). The single most
        suspicious edit shape — legitimate correction and "helping a
        student pass" look identical in isolation, so these are surfaced
        for a human to review, not auto-flagged as fraud.
      - large_jumps: any edit whose magnitude exceeds `min_edit_delta`
        percentage points, regardless of direction.
      - editor_rates: per-teacher edit rate (edits made ÷ scores they
        entered) so an editor who touches an unusually large share of their
        own entries stands out even without any single dramatic edit.

    All three lists are DESCRIPTIVE, not accusatory — the reason field on
    ScoreEditLog is included so a reviewer has context immediately.
    """
    log_filters = Q(exam_score__is_absent=False)
    if classroom_ids:
        if isinstance(classroom_ids, int):
            log_filters &= Q(exam_score__student__classroom_id=classroom_ids)
        else:
            log_filters &= Q(exam_score__student__classroom_id__in=classroom_ids)
    if subject_id:
        log_filters &= Q(exam_score__exam__subject_id=subject_id)
    if stream_id:
        log_filters &= Q(exam_score__student__stream_id=stream_id)
    if created_by_id:
        log_filters &= Q(exam_score__exam__created_by_id=created_by_id)

    logs = ScoreEditLog.objects.filter(log_filters).select_related(
        'exam_score__exam', 'exam_score__student__user', 'changed_by'
    ).order_by('-changed_at')

    boundary_crossings = []
    large_jumps = []
    editor_edit_counts = defaultdict(int)
    editor_names = {}

    for log in logs:
        exam = log.exam_score.exam
        max_score = float(exam.max_score) if exam.max_score else 0
        passing = float(exam.passing_score)
        if not max_score:
            continue

        old_pct = round((float(log.old_score) / max_score) * 100, 1)
        new_pct = round((float(log.new_score) / max_score) * 100, 1)
        passing_pct = round((passing / max_score) * 100, 1)
        delta = round(new_pct - old_pct, 1)

        editor_id = log.changed_by_id
        if editor_id:
            editor_edit_counts[editor_id] += 1
            if log.changed_by:
                editor_names[editor_id] = log.changed_by.get_full_name() or log.changed_by.email

        entry = {
            'edit_id': log.id,
            'student_name': log.exam_score.student.full_name,
            'exam_title': exam.title,
            'exam_date': str(exam.exam_date),
            'changed_by': editor_names.get(editor_id, 'Unknown'),
            'old_score': float(log.old_score),
            'new_score': float(log.new_score),
            'old_percentage': old_pct,
            'new_percentage': new_pct,
            'delta': delta,
            'reason': log.reason,
            'changed_at': str(log.changed_at),
        }

        if old_pct < passing_pct <= new_pct:
            boundary_crossings.append(entry)
        if abs(delta) >= min_edit_delta:
            large_jumps.append(entry)

    # Per-editor edit rate: edits made ÷ scores that editor has ever entered,
    # scoped by the same filters (so a teacher's rate is only measured
    # against their own entries, not the whole school's).
    entered_filters = Q(is_absent=False)
    if classroom_ids:
        if isinstance(classroom_ids, int):
            entered_filters &= Q(student__classroom_id=classroom_ids)
        else:
            entered_filters &= Q(student__classroom_id__in=classroom_ids)
    if subject_id:
        entered_filters &= Q(exam__subject_id=subject_id)
    if stream_id:
        entered_filters &= Q(student__stream_id=stream_id)
    if created_by_id:
        entered_filters &= Q(exam__created_by_id=created_by_id)

    entered_counts = defaultdict(int)
    for entered_by_id in ExamScore.objects.filter(entered_filters).values_list('entered_by_id', flat=True):
        if entered_by_id:
            entered_counts[entered_by_id] += 1

    editor_rates = []
    for editor_id, edit_count in editor_edit_counts.items():
        total_entered = entered_counts.get(editor_id, 0)
        rate = round((edit_count / total_entered) * 100, 1) if total_entered else None
        editor_rates.append({
            'teacher_id': editor_id,
            'teacher_name': editor_names.get(editor_id, 'Unknown'),
            'edits_made': edit_count,
            'scores_entered': total_entered,
            'edit_rate_percent': rate,
        })
    editor_rates.sort(key=lambda r: (r['edit_rate_percent'] or 0), reverse=True)

    return {
        'boundary_crossings': boundary_crossings,
        'boundary_crossing_count': len(boundary_crossings),
        'large_jumps': large_jumps,
        'large_jump_count': len(large_jumps),
        'editor_rates': editor_rates,
    }


def get_student_risk_score(
    student_id: int,
    subject_id: int = None,
    created_by_id: int = None,
) -> dict:
    """
    Feature 2 — Composite Risk Score.

    Replaces the binary at-risk rule (recent-3-avg < threshold OR a >10pt
    drop) with a weighted 0–100 score built from four independent signals,
    each returned so a teacher can see WHY a student is flagged rather than
    just THAT they are:

      - trend        (35%): recent trajectory (declining exams raise risk)
      - volatility   (20%): inconsistency across recent exams
      - topic_gap    (30%): how weak the student's weakest topics are
      - pass_margin  (15%): how far the recent average sits below a 45%
                             safety line (NECTA C boundary)

    Weights are deliberately front-loaded on trend and topic weakness,
    since those are the most actionable signals for a teacher.
    """
    filters = Q(student_id=student_id, is_absent=False)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('exam').order_by('exam__exam_date')
    percentages = [s.percentage for s in scores]

    if len(percentages) < 2:
        return {
            'student_id': student_id,
            'risk_score': None,
            'risk_level': 'insufficient_data',
            'factors': {},
        }

    recent = percentages[-5:]

    # trend component: negative slope → higher risk. Slope is in pct-points
    # per exam; a slope of -5 or steeper is treated as maximally risky.
    slope = _linear_slope(recent)
    trend_component = max(0.0, min(100.0, (-slope / 5.0) * 100))

    # volatility component: std dev of recent scores, capped at 25pts stdev
    # for a 100 score (very inconsistent performance).
    volatility = _std_dev(recent)
    volatility_component = max(0.0, min(100.0, (volatility / 25.0) * 100))

    # topic-gap component: average of the student's 3 weakest topics.
    topic_data = get_student_topic_analysis(student_id, subject_id=subject_id, created_by_id=created_by_id)
    weakest = sorted([t['average'] for t in topic_data.get('topics', [])])[:3]
    if weakest:
        topic_gap_component = max(0.0, min(100.0, 100 - (sum(weakest) / len(weakest))))
    else:
        topic_gap_component = None

    # pass-margin component: how far below the 45% (NECTA C) safety line.
    recent_avg = sum(recent) / len(recent)
    pass_margin_component = max(0.0, min(100.0, (45.0 - recent_avg) / 45.0 * 100))

    weights = {'trend': 0.35, 'volatility': 0.20, 'topic_gap': 0.30, 'pass_margin': 0.15}
    components = {
        'trend': trend_component,
        'volatility': volatility_component,
        'topic_gap': topic_gap_component,
        'pass_margin': pass_margin_component,
    }

    used_weight_sum = sum(weights[k] for k, v in components.items() if v is not None)
    if used_weight_sum == 0:
        composite = 0.0
    else:
        # Re-normalized weighted average: if a component is unavailable
        # (e.g. no topic data yet), the remaining weights are rescaled so
        # they still sum to 1 rather than silently under-counting risk.
        composite = sum(weights[k] * v for k, v in components.items() if v is not None) / used_weight_sum

    if composite >= 65:
        level = 'critical'
    elif composite >= 40:
        level = 'high'
    elif composite >= 20:
        level = 'moderate'
    else:
        level = 'low'

    return {
        'student_id': student_id,
        'risk_score': round(composite, 1),
        'risk_level': level,
        'factors': {
            'trend_contribution': round(trend_component * weights['trend'], 1),
            'volatility_contribution': round(volatility_component * weights['volatility'], 1),
            'topic_gap_contribution': round(topic_gap_component * weights['topic_gap'], 1) if topic_gap_component is not None else None,
            'pass_margin_contribution': round(pass_margin_component * weights['pass_margin'], 1),
            'recent_average': round(recent_avg, 1),
            'recent_trend_slope': slope,
            'volatility': round(volatility, 1),
            'weakest_topics_avg': round(sum(weakest) / len(weakest), 1) if weakest else None,
        },
    }


def get_classroom_risk_scores(
    classroom_id: int,
    subject_id: int = None,
    created_by_id: int = None,
    stream_id: int = None,
) -> dict:
    """Batch version of get_student_risk_score for every student in a classroom, sorted highest-risk first."""
    filters = Q(is_absent=False, student__classroom_id=classroom_id)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if stream_id:
        filters &= Q(student__stream_id=stream_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    # .order_by() clears ExamScore's default Meta ordering (-exam__exam_date),
    # which would otherwise be pulled into the SELECT and make .distinct()
    # a no-op — silently returning duplicate student_ids, one per exam.
    student_ids = ExamScore.objects.filter(filters).order_by().values_list('student_id', flat=True).distinct()
    names = {
        sp.id: sp.full_name
        for sp in StudentProfile.objects.filter(id__in=list(student_ids))
    }

    results = []
    for sid in student_ids:
        r = get_student_risk_score(sid, subject_id=subject_id, created_by_id=created_by_id)
        if r['risk_score'] is not None:
            r['student_name'] = names.get(sid, '')
            results.append(r)

    results.sort(key=lambda r: r['risk_score'], reverse=True)
    return {'classroom_id': classroom_id, 'students': results}


def get_topic_dependency_chains(
    classroom_id: int = None,
    subject_id: int = None,
    created_by_id: int = None,
    weak_threshold: float = 45.0,
    min_sample: int = 5,
    stream_id: int = None,
) -> dict:
    """
    Feature 3 — Root-Cause Topic Dependency Chains.

    For every ordered pair of topics (A, B), compares:
      - baseline_weak_rate: fraction of ALL students weak in B (avg < threshold)
      - conditional_weak_rate: fraction of students who are weak in A that
        are ALSO weak in B

    A `lift` > 1 means weakness in A predicts weakness in B more than the
    base rate alone would suggest — i.e. a candidate root-cause dependency
    (e.g. "students weak in Fractions are 2.4x more likely to also be weak
    in Algebra"). Only pairs with at least `min_sample` co-occurring
    students are reported, to avoid noise from small classes.
    """
    filters = Q(exam_score__is_absent=False)
    if classroom_id:
        filters &= Q(exam_score__student__classroom_id=classroom_id)
    if subject_id:
        filters &= Q(topic__subject_id=subject_id)
    if stream_id:
        filters &= Q(exam_score__student__stream_id=stream_id)
    if created_by_id:
        filters &= Q(exam_score__exam__created_by_id=created_by_id)

    topic_scores = TopicScore.objects.filter(filters).select_related('topic', 'exam_score')

    student_topic_pcts = defaultdict(lambda: defaultdict(list))
    topic_names = {}
    for ts in topic_scores:
        student_topic_pcts[ts.exam_score.student_id][ts.topic_id].append(ts.percentage)
        topic_names[ts.topic_id] = ts.topic.name

    # Average per student per topic, then classify weak/not-weak.
    student_topic_avg = {
        sid: {tid: sum(pcts) / len(pcts) for tid, pcts in topics.items()}
        for sid, topics in student_topic_pcts.items()
    }

    topic_ids = list(topic_names.keys())
    weak_students_by_topic = {
        tid: {sid for sid, avgs in student_topic_avg.items() if tid in avgs and avgs[tid] < weak_threshold}
        for tid in topic_ids
    }
    all_students_by_topic = {
        tid: {sid for sid, avgs in student_topic_avg.items() if tid in avgs}
        for tid in topic_ids
    }

    chains = []
    for a in topic_ids:
        weak_in_a = weak_students_by_topic[a]
        if len(weak_in_a) < min_sample:
            continue
        for b in topic_ids:
            if a == b:
                continue
            eligible_for_b = all_students_by_topic[b]
            weak_in_a_and_eligible_for_b = weak_in_a & eligible_for_b
            if len(weak_in_a_and_eligible_for_b) < min_sample:
                continue

            baseline_pool = eligible_for_b
            baseline_weak_rate = len(weak_students_by_topic[b] & baseline_pool) / len(baseline_pool) if baseline_pool else 0

            conditional_weak = weak_in_a_and_eligible_for_b & weak_students_by_topic[b]
            conditional_weak_rate = len(conditional_weak) / len(weak_in_a_and_eligible_for_b)

            lift = round(conditional_weak_rate / baseline_weak_rate, 2) if baseline_weak_rate > 0 else None
            if lift is None or lift <= 1.3:
                continue

            chains.append({
                'from_topic': topic_names[a],
                'to_topic': topic_names[b],
                'baseline_weak_rate': round(baseline_weak_rate * 100, 1),
                'conditional_weak_rate': round(conditional_weak_rate * 100, 1),
                'lift': lift,
                'sample_size': len(weak_in_a_and_eligible_for_b),
            })

    chains.sort(key=lambda c: c['lift'], reverse=True)
    return {'classroom_id': classroom_id, 'dependency_chains': chains[:25]}


def get_teacher_grading_consistency(
    subject_id: int = None,
    academic_year: str = None,
    term: str = None,
) -> dict:
    """
    Feature 4 — Teacher Grading Consistency Audit (admin-only; call from a
    view gated to super_admin — this function itself is not scoped by
    created_by_id since it exists to COMPARE across teachers).

    For each (topic, teacher) pair, computes the teacher's average score on
    that topic and a z-score against the population of all teachers who
    have graded that topic. Teachers with |z| >= 1.5 on a topic (min 5
    graded scores) are flagged as grading meaningfully more leniently or
    harshly than their peers on the same material — a leading indicator of
    grading inconsistency that would otherwise only surface as unexplained
    classroom-average differences.
    """
    filters = Q(exam_score__is_absent=False)
    if subject_id:
        filters &= Q(topic__subject_id=subject_id)
    if academic_year:
        filters &= Q(exam_score__exam__academic_year=academic_year)
    if term:
        filters &= Q(exam_score__exam__term=term)

    rows = TopicScore.objects.filter(filters).select_related(
        'topic', 'exam_score__exam__created_by'
    ).values_list(
        'topic_id', 'topic__name', 'exam_score__exam__created_by_id',
        'exam_score__exam__created_by__first_name', 'exam_score__exam__created_by__last_name',
        'exam_score__exam__created_by__email', 'score', 'max_marks',
    )

    # topic_id -> teacher_id -> [pcts]
    data = defaultdict(lambda: defaultdict(list))
    topic_names = {}
    teacher_names = {}

    for tid, tname, teacher_id, fn, ln, email, score, max_marks in rows:
        if not max_marks or not teacher_id:
            continue
        pct = round((float(score) / float(max_marks)) * 100, 1)
        data[tid][teacher_id].append(pct)
        topic_names[tid] = tname
        teacher_names[teacher_id] = (f'{fn} {ln}'.strip() or email)

    flags = []
    for tid, by_teacher in data.items():
        teacher_avgs = {
            teacher_id: sum(pcts) / len(pcts)
            for teacher_id, pcts in by_teacher.items() if len(pcts) >= 5
        }
        if len(teacher_avgs) < 2:
            continue  # need at least 2 teachers to compare
        pop_values = list(teacher_avgs.values())
        pop_mean = sum(pop_values) / len(pop_values)
        pop_std = _std_dev(pop_values)
        if pop_std == 0:
            continue

        for teacher_id, avg in teacher_avgs.items():
            z = round((avg - pop_mean) / pop_std, 2)
            if abs(z) >= 1.5:
                flags.append({
                    'topic': topic_names[tid],
                    'teacher_id': teacher_id,
                    'teacher_name': teacher_names[teacher_id],
                    'teacher_average': round(avg, 1),
                    'peer_average': round(pop_mean, 1),
                    'z_score': z,
                    'direction': 'lenient' if z > 0 else 'harsh',
                    'sample_size': len(by_teacher[teacher_id]),
                })

    flags.sort(key=lambda f: abs(f['z_score']), reverse=True)
    return {'flags': flags, 'flag_count': len(flags)}


def get_grade_boundary_whatif(
    student_id: int,
    subject_id: int = None,
    created_by_id: int = None,
) -> dict:
    """
    Feature 5 — Grade-Boundary Sensitivity ("What-If") Engine.

    Finds the NECTA grade boundary the student is currently closest to
    (using the same regression-based prediction as _predict_necta_grade),
    then ranks the student's topics by (weakness × exam weight) to show
    which specific topic improvement would close that gap fastest —
    turning the prediction from a label into a concrete teaching action.
    """
    filters = Q(student_id=student_id, is_absent=False)
    if subject_id:
        filters &= Q(exam__subject_id=subject_id)
    if created_by_id:
        filters &= Q(exam__created_by_id=created_by_id)

    scores = ExamScore.objects.filter(filters).select_related('exam').order_by('exam__exam_date')
    percentages = [s.percentage for s in scores]
    if len(percentages) < 3:
        return {'student_id': student_id, 'status': 'insufficient_data'}

    recent = percentages[-6:]
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(recent))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den else 0
    predicted = max(0.0, min(100.0, y_mean + slope * n))

    boundaries = [('A', 75.0), ('B', 65.0), ('C', 45.0), ('D', 30.0)]
    current_grade = _predict_necta_grade(percentages)

    # distance to the next boundary UP (the grade the student could reach)
    next_boundary = None
    for grade, cutoff in boundaries:
        if predicted < cutoff:
            next_boundary = (grade, cutoff)
    gap = round(next_boundary[1] - predicted, 1) if next_boundary else 0.0

    # weight each topic by its average ExamTopicWeight.weight_percentage
    # across this student's exams, so a topic that's both weak AND heavily
    # weighted rises to the top of the recommendation list.
    exam_ids = list(scores.values_list('exam_id', flat=True))
    weight_rows = ExamTopicWeight.objects.filter(exam_id__in=exam_ids).values_list('topic_id', 'weight_percentage')
    topic_weight_sum = defaultdict(float)
    topic_weight_count = defaultdict(int)
    for tid, w in weight_rows:
        topic_weight_sum[tid] += float(w)
        topic_weight_count[tid] += 1
    avg_weight = {
        tid: topic_weight_sum[tid] / topic_weight_count[tid]
        for tid in topic_weight_sum if topic_weight_count[tid]
    }

    topic_data = get_student_topic_analysis(student_id, subject_id=subject_id, created_by_id=created_by_id)
    recommendations = []
    for t in topic_data.get('topics', []):
        weight = avg_weight.get(t['topic_id'], 1.0)
        weakness = max(0.0, 100 - t['average'])
        priority_score = round(weakness * weight, 1)
        recommendations.append({
            'topic_name': t['topic_name'],
            'current_average': t['average'],
            'exam_weight_percent': round(weight, 1),
            'priority_score': priority_score,
        })
    recommendations.sort(key=lambda r: r['priority_score'], reverse=True)

    return {
        'student_id': student_id,
        'predicted_average': round(predicted, 1),
        'predicted_grade': current_grade,
        'next_grade': next_boundary[0] if next_boundary else None,
        'points_needed': gap,
        'priority_topics': recommendations[:5],
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _predict_necta_grade(percentages: list) -> str | None:
    """Simple linear regression on last 6 exams to predict final NECTA grade."""
    if len(percentages) < 3:
        return None
    recent = percentages[-6:]
    n = len(recent)
    x_mean = (n - 1) / 2
    y_mean = sum(recent) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(recent))
    den = sum((i - x_mean) ** 2 for i in range(n))
    slope = num / den if den else 0
    predicted = max(0, min(100, y_mean + slope * n))
    if predicted >= 75: return 'A'
    if predicted >= 65: return 'B'
    if predicted >= 45: return 'C'
    if predicted >= 30: return 'D'
    return 'F'


def _calculate_trend(percentages: list) -> str:
    if len(percentages) < 2:
        return 'stable'
    slope = _linear_slope(percentages)
    if slope > 2: return 'improving'
    if slope < -2: return 'declining'
    return 'stable'


def _linear_slope(values: list) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return round(numerator / denominator, 4) if denominator else 0.0


def _moving_average(values: list, window: int = 3) -> list:
    result = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1):i + 1]
        result.append(round(sum(chunk) / len(chunk), 1))
    return result


def _std_dev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5


def _score_distribution(percentages: list) -> dict:
    buckets = {'0-49': 0, '50-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0}
    for p in percentages:
        if p < 50: buckets['0-49'] += 1
        elif p < 60: buckets['50-59'] += 1
        elif p < 70: buckets['60-69'] += 1
        elif p < 80: buckets['70-79'] += 1
        elif p < 90: buckets['80-89'] += 1
        else: buckets['90-100'] += 1
    return buckets
