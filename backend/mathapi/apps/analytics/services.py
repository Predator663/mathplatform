"""
Analytics computation services.
All heavy data processing lives here, keeping views thin.
"""
from django.db.models import Avg, Max, Min, Count, Q, F
from django.db.models.functions import Round
from collections import defaultdict
from mathapi.apps.exams.models import ExamScore, TopicScore, Exam
from mathapi.apps.students.models import StudentProfile, Classroom


def get_student_summary(student_id: int) -> dict:
    """Top-level performance summary for one student."""
    try:
        student = StudentProfile.objects.select_related('user', 'classroom').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return {}

    scores = ExamScore.objects.filter(
        student=student, is_absent=False
    ).select_related('exam').order_by('exam__exam_date')

    if not scores.exists():
        return {
            'student_id': student_id,
            'student_name': student.full_name,
            'total_exams': 0,
            'average_percentage': None,
            'trend': 'no_data',
        }

    percentages = [s.percentage for s in scores]
    passed = [s for s in scores if s.passed]

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


def get_student_trend(student_id: int, exam_type: str = None, term: str = None) -> dict:
    """Full score timeline and trend analysis for a student."""
    filters = Q(student_id=student_id, is_absent=False)
    if exam_type:
        filters &= Q(exam__exam_type=exam_type)
    if term:
        filters &= Q(exam__term=term)

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


def get_student_topic_analysis(student_id: int) -> dict:
    """Per-topic mastery breakdown for a student."""
    topic_scores = TopicScore.objects.filter(
        exam_score__student_id=student_id,
        exam_score__is_absent=False,
    ).select_related('topic', 'exam_score__exam').order_by('exam_score__exam__exam_date')

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


def get_class_analytics(classroom_id: int, academic_year: str = None, term: str = None) -> dict:
    """Class-wide performance analytics."""
    try:
        classroom = Classroom.objects.select_related('grade_level').get(id=classroom_id)
    except Classroom.DoesNotExist:
        return {}

    filters = Q(student__classroom_id=classroom_id, is_absent=False)
    exam_filters = Q(classrooms=classroom)
    if academic_year:
        filters &= Q(exam__academic_year=academic_year)
        exam_filters &= Q(academic_year=academic_year)
    if term:
        filters &= Q(exam__term=term)
        exam_filters &= Q(term=term)

    exams = Exam.objects.filter(exam_filters).order_by('exam_date')
    exam_summaries = []

    for exam in exams:
        exam_scores = ExamScore.objects.filter(exam=exam, student__classroom_id=classroom_id, is_absent=False)
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
            'student_count': len(pcts),
            'average': round(sum(pcts) / len(pcts), 1),
            'highest': round(max(pcts), 1),
            'lowest': round(min(pcts), 1),
            'pass_rate': round((len(passed) / len(pcts)) * 100, 1),
            'std_dev': round(_std_dev(pcts), 1),
        })

    # All scores for the class
    all_scores = ExamScore.objects.filter(filters)
    all_pcts = [s.percentage for s in all_scores]

    # Student rankings
    student_avgs = defaultdict(list)
    for s in all_scores:
        student_avgs[s.student_id].append(s.percentage)

    rankings = []
    for sid, pcts_list in student_avgs.items():
        try:
            sp = StudentProfile.objects.select_related('user').get(id=sid)
            rankings.append({
                'student_id': sid,
                'student_name': sp.full_name,
                'student_code': sp.student_id,
                'average': round(sum(pcts_list) / len(pcts_list), 1),
                'exams_taken': len(pcts_list),
            })
        except StudentProfile.DoesNotExist:
            continue

    rankings.sort(key=lambda x: x['average'], reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1

    return {
        'classroom_id': classroom_id,
        'classroom_name': str(classroom),
        'grade_level': classroom.grade_level.name,
        'exam_summaries': exam_summaries,
        'overall_average': round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else None,
        'student_rankings': rankings,
        'at_risk_students': [r for r in rankings if r['average'] < 50],
        'top_performers': rankings[:5],
        'distribution': _score_distribution(all_pcts),
    }


def get_topic_class_heatmap(classroom_id: int, academic_year: str = None) -> dict:
    """Heatmap: students × topics showing average mastery."""
    filters = Q(
        exam_score__student__classroom_id=classroom_id,
        exam_score__is_absent=False,
    )
    if academic_year:
        filters &= Q(exam_score__exam__academic_year=academic_year)

    topic_scores = TopicScore.objects.filter(filters).select_related(
        'topic', 'exam_score__student__user'
    )

    # Build matrix: student_id -> topic_id -> list of percentages
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
        for tid, topic_info in topics.items():
            pcts = matrix[sid].get(tid, [])
            row['topics'][tid] = round(sum(pcts) / len(pcts), 1) if pcts else None
        heatmap_rows.append(row)

    return {
        'classroom_id': classroom_id,
        'topics': list(topics.values()),
        'rows': heatmap_rows,
    }


def get_at_risk_students(classroom_id: int = None, threshold: float = 50.0) -> list:
    """Return students flagged as at risk based on recent performance."""
    filters = Q(is_absent=False)
    if classroom_id:
        filters &= Q(student__classroom_id=classroom_id)

    # Get last 3 exams per student
    scores = ExamScore.objects.filter(filters).select_related(
        'student__user', 'exam'
    ).order_by('student_id', '-exam__exam_date')

    student_recent = defaultdict(list)
    for s in scores:
        if len(student_recent[s.student_id]) < 3:
            student_recent[s.student_id].append(s.percentage)

    at_risk = []
    for sid, recent_pcts in student_recent.items():
        if not recent_pcts:
            continue
        avg = sum(recent_pcts) / len(recent_pcts)
        declining = len(recent_pcts) >= 2 and recent_pcts[0] < recent_pcts[-1] - 10
        if avg < threshold or declining:
            try:
                sp = StudentProfile.objects.select_related('user', 'classroom').get(id=sid)
                at_risk.append({
                    'student_id': sid,
                    'student_name': sp.full_name,
                    'student_code': sp.student_id,
                    'classroom': str(sp.classroom) if sp.classroom else None,
                    'recent_average': round(avg, 1),
                    'recent_scores': recent_pcts,
                    'flags': {
                        'below_threshold': avg < threshold,
                        'declining': declining,
                    }
                })
            except StudentProfile.DoesNotExist:
                continue

    at_risk.sort(key=lambda x: x['recent_average'])
    return at_risk


def get_comparative_analysis(classroom_ids: list, academic_year: str = None, term: str = None) -> dict:
    """Compare performance across multiple classrooms."""
    results = []
    for cid in classroom_ids:
        data = get_class_analytics(cid, academic_year=academic_year, term=term)
        if data:
            results.append({
                'classroom_id': cid,
                'classroom_name': data.get('classroom_name'),
                'overall_average': data.get('overall_average'),
                'exam_summaries': data.get('exam_summaries', []),
            })
    return {'comparisons': results}


# ── Private helpers ──────────────────────────────────────────────────────────

def _calculate_trend(percentages: list) -> str:
    if len(percentages) < 2:
        return 'stable'
    slope = _linear_slope(percentages)
    if slope > 2:
        return 'improving'
    if slope < -2:
        return 'declining'
    return 'stable'


def _linear_slope(values: list) -> float:
    """Simple linear regression slope."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _moving_average(values: list, window: int = 3) -> list:
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start:i + 1]
        result.append(round(sum(chunk) / len(chunk), 1))
    return result


def _std_dev(values: list) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5


def _score_distribution(percentages: list) -> dict:
    buckets = {'0-49': 0, '50-59': 0, '60-69': 0, '70-79': 0, '80-89': 0, '90-100': 0}
    for p in percentages:
        if p < 50:
            buckets['0-49'] += 1
        elif p < 60:
            buckets['50-59'] += 1
        elif p < 70:
            buckets['60-69'] += 1
        elif p < 80:
            buckets['70-79'] += 1
        elif p < 90:
            buckets['80-89'] += 1
        else:
            buckets['90-100'] += 1
    return buckets
