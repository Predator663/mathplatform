"""
Student-vs-student comparison — built for the "call a student in and show
them how they're growing, alongside a peer" use case: each student's own
exam summary/trend/topic breakdown, computed with the exact same functions
the single-student analytics pages use, plus a simple "growth" figure
(first exam % -> most recent exam %) so the comparison reads as a growth
story rather than a bare ranking.
"""
from mathapi.apps.students.models import StudentProfile
from . import services as analytics_services


def _growth(timeline: list) -> dict:
    """First-exam vs most-recent-exam percentage — deliberately the
    simplest possible "have they grown" figure, easy to say out loud in a
    1:1 conversation. Returns Nones if there's fewer than 2 exams."""
    if len(timeline) < 2:
        return {'first_pct': None, 'last_pct': None, 'delta': None}
    first_pct = timeline[0]['percentage']
    last_pct = timeline[-1]['percentage']
    return {
        'first_pct': first_pct, 'last_pct': last_pct,
        'delta': round(last_pct - first_pct, 1),
    }


def get_student_comparison_profile(student_id: int, *, subject_id=None,
                                    created_by_id=None, include_quizzes=False) -> dict:
    """One student's full comparison profile: identity, exam summary,
    exam trend, topic breakdown, growth, and (optionally) quiz streak/
    badge counts. Returns None if the student doesn't exist."""
    try:
        student = StudentProfile.objects.select_related('classroom').get(id=student_id)
    except StudentProfile.DoesNotExist:
        return None

    summary = analytics_services.get_student_summary(student_id, subject_id=subject_id, created_by_id=created_by_id)
    trend = analytics_services.get_student_trend(student_id, subject_id=subject_id, created_by_id=created_by_id)
    topics = analytics_services.get_student_topic_analysis(student_id, subject_id=subject_id, created_by_id=created_by_id)

    profile = {
        'student_id': student_id,
        'name': student.full_name,
        'student_code': student.student_id,
        'classroom': str(student.classroom) if student.classroom else None,
        'summary': summary,
        'timeline': trend['timeline'],
        'trend': trend['trend'],
        'moving_average': trend['moving_average'],
        'topics': topics['topics'],
        'growth': _growth(trend['timeline']),
        'quiz_streak': None,
        'badge_count': None,
    }

    if include_quizzes:
        from mathapi.apps.quizzes import analytics_services as quiz_analytics_services
        from mathapi.apps.gamification import services as gamification_services

        quiz_progress = quiz_analytics_services.get_student_quiz_topic_progress(
            student_id, subject_id=subject_id, created_by_id=created_by_id,
        )
        quiz_gamified = gamification_services.get_student_quiz_progress(student)
        exam_gamified = gamification_services.get_student_progress(student)

        profile['quiz_summary'] = quiz_progress['summary']
        profile['quiz_topics'] = quiz_progress['topic_data']
        profile['quiz_streak'] = quiz_gamified['streak'].current_streak
        profile['badge_count'] = len(exam_gamified['badges'])

    return profile


def get_students_comparison(student_ids: list, *, subject_id=None,
                             created_by_id=None, include_quizzes=False) -> dict:
    """Builds comparison profiles for every id in student_ids, in the
    order given (callers rely on this order for consistent chart colors).
    `missing_ids` lists any ids that didn't resolve to a real student —
    the caller decides whether that's fatal."""
    profiles = []
    missing_ids = []
    for sid in student_ids:
        profile = get_student_comparison_profile(
            sid, subject_id=subject_id, created_by_id=created_by_id, include_quizzes=include_quizzes,
        )
        if profile is None:
            missing_ids.append(sid)
        else:
            profiles.append(profile)
    return {'students': profiles, 'missing_ids': missing_ids}
