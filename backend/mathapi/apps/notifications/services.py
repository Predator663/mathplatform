"""
Email notification engine.

Design principles:
  - No separate "notification rules" table to keep in sync with reality —
    every trigger re-runs the SAME analytics.services functions the
    dashboard pages already use (get_at_risk_students, get_classroom_risk_scores,
    get_integrity_flags), so "what counts as at-risk" only ever needs to be
    defined once.
  - Every send is logged to NotificationLog, which doubles as both the
    cooldown/dedupe source (don't re-email the same ongoing situation every
    time the alert command runs) and the in-app notification history.
  - Preferences are read lazily against DEFAULT_FREQUENCY_BY_ROLE — a user
    only gets a database row once they've actually changed something.
  - Email delivery failures are caught and logged, never raised — a bad
    SMTP config should never block the action that triggered the email
    (e.g. publishing an exam).
"""
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from mathapi.apps.accounts.models import User, SiteSettings, TeacherAssignment
from mathapi.apps.students.models import StudentProfile, Classroom, ParentStudentLink
from mathapi.apps.exams.models import Exam, ExamScore
from mathapi.apps.analytics import services as analytics_services

from .models import (
    NotificationPreference, NotificationLog, NotificationCategory,
    DEFAULT_FREQUENCY_BY_ROLE,
)

AT_RISK_COOLDOWN_DAYS = 3
RISK_CRITICAL_COOLDOWN_DAYS = 5
INTEGRITY_COOLDOWN_DAYS = 1
EXAM_PUBLISHED_COOLDOWN_DAYS = 1
DIGEST_COOLDOWN_DAYS = 1
TOURNAMENT_RESULT_COOLDOWN_DAYS = 1


# ── Preferences ──────────────────────────────────────────────────────────

def get_frequency(user, category: str) -> str:
    pref = NotificationPreference.objects.filter(user=user, category=category).first()
    if pref:
        return pref.frequency
    return DEFAULT_FREQUENCY_BY_ROLE.get(user.role, {}).get(category, 'immediate')


def get_frequencies_map(users, category: str) -> dict:
    """Batch version of get_frequency — one query for overrides instead of N."""
    users = list(users)
    overrides = {
        p.user_id: p.frequency
        for p in NotificationPreference.objects.filter(user__in=users, category=category)
    }
    return {
        u.id: overrides.get(u.id, DEFAULT_FREQUENCY_BY_ROLE.get(u.role, {}).get(category, 'immediate'))
        for u in users
    }


# ── Core send engine ─────────────────────────────────────────────────────

def _recently_notified(recipient, category, related_object_type, related_object_id, cooldown_days) -> bool:
    since = timezone.now() - timedelta(days=cooldown_days)
    return NotificationLog.objects.filter(
        recipient=recipient, category=category,
        related_object_type=related_object_type, related_object_id=related_object_id,
        status=NotificationLog.Status.SENT, sent_at__gte=since,
    ).exists()


def send_notification(
    *, recipient, category: str, subject: str, template_base: str, context: dict,
    related_object_type: str = '', related_object_id: int = None,
    summary: str = '', cooldown_days: int = None,
) -> bool:
    """
    Low-level send: renders the HTML+text pair, emails, and logs the
    attempt. Does NOT check the recipient's frequency preference — callers
    decide whether to invoke this at all via get_frequency() first, since
    the right behaviour differs per category (a 'digest' preference means
    "don't call this now, a digest job will cover it later", not "skip").
    """
    if not recipient.email:
        return False

    if cooldown_days and related_object_id is not None:
        if _recently_notified(recipient, category, related_object_type, related_object_id, cooldown_days):
            return False

    site = SiteSettings.get()
    full_context = {
        **context,
        'subject': subject,
        'platform_name': site.platform_name,
        'logo_url': site.logo_url,
        'logo_letter': site.logo_letter,
        'footer_text': site.footer_text,
        'category_label': NotificationCategory(category).label,
        'preferences_url': f'{settings.FRONTEND_URL}/settings/notifications',
    }

    try:
        html_body = render_to_string(f'notifications/{template_base}.html', full_context)
        text_body = render_to_string(f'notifications/{template_base}.txt', full_context)
        msg = EmailMultiAlternatives(subject, text_body, settings.DEFAULT_FROM_EMAIL, [recipient.email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception as exc:
        NotificationLog.objects.create(
            recipient=recipient, category=category, subject=subject, summary=summary[:500],
            related_object_type=related_object_type, related_object_id=related_object_id,
            status=NotificationLog.Status.FAILED, error_message=str(exc)[:2000],
        )
        return False

    NotificationLog.objects.create(
        recipient=recipient, category=category, subject=subject, summary=summary[:500],
        related_object_type=related_object_type, related_object_id=related_object_id,
        status=NotificationLog.Status.SENT,
    )
    return True


def send_test_email(recipient, triggered_by: str) -> bool:
    site = SiteSettings.get()
    return send_notification(
        recipient=recipient,
        category=NotificationCategory.TEST,
        subject=f'Test email from {site.platform_name}',
        template_base='test_email',
        context={
            'recipient_email': recipient.email,
            'sent_at_display': timezone.now().strftime('%d %b %Y, %H:%M'),
            'triggered_by': triggered_by,
        },
        summary='Test email — confirms SMTP delivery is working',
    )


# ── Trigger: exam published ─────────────────────────────────────────────

def notify_exam_published(exam: Exam) -> int:
    """
    Called right after an exam is marked published. Emails the exam's
    creator (a confirmation their submission went live — skipped if an
    admin published their own exam) and every parent with an 'immediate'
    preference, one email each, scoped to just their own child's classroom
    and score. Parents on 'digest' pick this exam up in tomorrow's summary
    instead of getting an email right now.
    """
    site = SiteSettings.get()
    classrooms = list(exam.classrooms.all())
    classroom_names = ', '.join(str(c) for c in classrooms) or '—'
    sent = 0

    if exam.created_by_id and exam.created_by.role == 'teacher':
        creator = exam.created_by
        if get_frequency(creator, NotificationCategory.EXAM_PUBLISHED) == 'immediate':
            sent += int(send_notification(
                recipient=creator,
                category=NotificationCategory.EXAM_PUBLISHED,
                subject=f'"{exam.title}" has been published — {site.platform_name}',
                template_base='exam_published',
                context={
                    'greeting': f'Hi {creator.first_name or creator.get_full_name()},',
                    'exam_title': exam.title,
                    'classroom_name': classroom_names,
                    'subject_name': exam.subject.name if exam.subject else '—',
                    'exam_type_label': exam.get_exam_type_display(),
                    'term_label': exam.get_term_display(),
                    'exam_date_display': exam.exam_date.strftime('%d %b %Y'),
                    'passing_percentage_display': f'{exam.passing_percentage}%',
                    'is_creator': True, 'student_first_name': '', 'score_recorded': False,
                    'action_label': 'View exam',
                    'action_url': f'{settings.FRONTEND_URL}/exams/{exam.id}',
                },
                related_object_type='exam', related_object_id=exam.id,
                summary=f'"{exam.title}" published',
                cooldown_days=EXAM_PUBLISHED_COOLDOWN_DAYS,
            ))

    if not classrooms:
        return sent

    students = StudentProfile.objects.filter(classroom__in=classrooms, is_active=True).select_related('user', 'classroom')
    links = (ParentStudentLink.objects.filter(student__in=students)
             .select_related('parent', 'student', 'student__classroom'))
    parents = {link.parent_id: link.parent for link in links if link.parent.is_active}
    freq_map = get_frequencies_map(parents.values(), NotificationCategory.EXAM_PUBLISHED)

    for link in links:
        parent = parents.get(link.parent_id)
        if not parent or freq_map.get(parent.id) != 'immediate':
            continue
        student = link.student
        score = ExamScore.objects.filter(exam=exam, student=student, is_absent=False).first()
        sent += int(send_notification(
            recipient=parent,
            category=NotificationCategory.EXAM_PUBLISHED,
            subject=f'{student.full_name}: new exam published — {site.platform_name}',
            template_base='exam_published',
            context={
                'greeting': f'Hi {parent.first_name or parent.get_full_name()},',
                'exam_title': exam.title,
                'classroom_name': str(student.classroom) if student.classroom else classroom_names,
                'subject_name': exam.subject.name if exam.subject else '—',
                'exam_type_label': exam.get_exam_type_display(),
                'term_label': exam.get_term_display(),
                'exam_date_display': exam.exam_date.strftime('%d %b %Y'),
                'passing_percentage_display': f'{exam.passing_percentage}%',
                'is_creator': False,
                'student_first_name': student.user.first_name or student.full_name.split(' ')[0],
                'score_recorded': bool(score),
                'score_display': f'{score.percentage}%' if score else '',
                'score_color': '#16a34a' if (score and score.passed) else '#e11d48',
                'action_label': 'View result',
                'action_url': f'{settings.FRONTEND_URL}/analytics/student/{student.id}',
            },
            related_object_type='exam', related_object_id=exam.id,
            summary=f'{student.full_name}: "{exam.title}" published',
            cooldown_days=EXAM_PUBLISHED_COOLDOWN_DAYS,
        ))

    return sent


# ── Trigger: at-risk ─────────────────────────────────────────────────────

def _recipients_for_student(student_profile: StudentProfile):
    recipients = []
    if student_profile.classroom_id:
        teacher_ids = (TeacherAssignment.objects.filter(classroom_id=student_profile.classroom_id)
                       .values_list('teacher_id', flat=True).distinct())
        recipients += list(User.objects.filter(id__in=teacher_ids, is_active=True))
    recipients += [
        link.parent for link in ParentStudentLink.objects.filter(student=student_profile).select_related('parent')
        if link.parent.is_active
    ]
    return recipients


def notify_at_risk_student(row: dict, student_profile: StudentProfile) -> int:
    """row: one entry from analytics.services.get_at_risk_students()."""
    site = SiteSettings.get()
    classroom = student_profile.classroom
    recent_scores = row['recent_scores']
    declining = row['flags']['declining']
    first_name = student_profile.user.first_name or student_profile.full_name.split(' ')[0]
    sent = 0

    for recipient in _recipients_for_student(student_profile):
        if get_frequency(recipient, NotificationCategory.AT_RISK) != 'immediate':
            continue
        is_parent = recipient.role == 'parent'
        sent += int(send_notification(
            recipient=recipient,
            category=NotificationCategory.AT_RISK,
            subject=f'{student_profile.full_name} flagged at-risk — {site.platform_name}',
            template_base='at_risk_alert',
            context={
                'greeting': f'Hi {recipient.first_name or recipient.get_full_name()},',
                'student_name': student_profile.full_name,
                'student_first_name': first_name,
                'classroom_name': str(classroom) if classroom else '—',
                'exams_taken': len(recent_scores),
                'declining': declining,
                'threshold': 30,
                'recent_average_display': f"{row['recent_average']}%",
                'trend_label': 'Declining' if declining else 'Below threshold',
                'trend_color': '#e11d48' if declining else '#b45309',
                'recent_scores': recent_scores,
                'recent_scores_display': '  →  '.join(f'{p}%' for p in recent_scores),
                'is_parent': is_parent,
                'action_label': 'View student' if is_parent else 'Open At-Risk Tracker',
                'action_url': (
                    f'{settings.FRONTEND_URL}/analytics/student/{student_profile.id}' if is_parent
                    else f'{settings.FRONTEND_URL}/at-risk?classroom_id={classroom.id}' if classroom
                    else f'{settings.FRONTEND_URL}/at-risk'
                ),
            },
            related_object_type='student', related_object_id=student_profile.id,
            summary=f'{student_profile.full_name}: recent avg {row["recent_average"]}%',
            cooldown_days=AT_RISK_COOLDOWN_DAYS,
        ))
    return sent


# ── Trigger: critical composite risk score ──────────────────────────────

_FACTOR_LABELS = {
    'trend_contribution': ('Trend', 'a declining trajectory'),
    'volatility_contribution': ('Volatility', 'inconsistent scores across exams'),
    'topic_gap_contribution': ('Topic gaps', 'weak mastery in their weakest topics'),
    'pass_margin_contribution': ('Pass margin', 'sitting well below the 45% safety line'),
}


def notify_critical_risk(risk_row: dict, student_profile: StudentProfile) -> int:
    """risk_row: one entry from get_classroom_risk_scores()['students'] with risk_level == 'critical'."""
    site = SiteSettings.get()
    classroom = student_profile.classroom
    factors = risk_row['factors']

    contributions = sorted(
        ((k, factors[k]) for k in _FACTOR_LABELS if factors.get(k) is not None),
        key=lambda kv: kv[1], reverse=True,
    )
    risk_factors_ctx = [
        {'label': _FACTOR_LABELS[k][0], 'display': f'{v} pts', 'color': '#e11d48' if v >= 15 else '#b45309'}
        for k, v in contributions
    ]
    if contributions:
        top_key, _ = contributions[0]
        primary_driver_explanation = (
            f'The biggest driver right now is {_FACTOR_LABELS[top_key][1]}. Recent average sits at '
            f"{factors.get('recent_average')}%"
            + (f", with their weakest topics averaging {factors.get('weakest_topics_avg')}%."
               if factors.get('weakest_topics_avg') is not None else '.')
        )
    else:
        primary_driver_explanation = 'Multiple factors are contributing roughly equally — see the breakdown above.'

    sent = 0
    for recipient in _recipients_for_student(student_profile):
        if get_frequency(recipient, NotificationCategory.RISK_CRITICAL) != 'immediate':
            continue
        sent += int(send_notification(
            recipient=recipient,
            category=NotificationCategory.RISK_CRITICAL,
            subject=f'{student_profile.full_name}: risk score now critical — {site.platform_name}',
            template_base='risk_critical_alert',
            context={
                'greeting': f'Hi {recipient.first_name or recipient.get_full_name()},',
                'student_name': student_profile.full_name,
                'student_first_name': student_profile.user.first_name or student_profile.full_name.split(' ')[0],
                'classroom_name': str(classroom) if classroom else '—',
                'risk_score': risk_row['risk_score'],
                'risk_factors': risk_factors_ctx,
                'primary_driver_explanation': primary_driver_explanation,
                'action_label': 'View risk breakdown',
                'action_url': f'{settings.FRONTEND_URL}/analytics/student/{student_profile.id}',
            },
            related_object_type='student_critical', related_object_id=student_profile.id,
            summary=f'{student_profile.full_name}: risk score {risk_row["risk_score"]}/100',
            cooldown_days=RISK_CRITICAL_COOLDOWN_DAYS,
        ))
    return sent


# ── Trigger: integrity flags (admin only) ───────────────────────────────

def notify_integrity_flags(flags_data: dict) -> int:
    """flags_data: return value of analytics.services.get_integrity_flags() (global scan)."""
    boundary = flags_data.get('boundary_crossings', [])
    large = flags_data.get('large_jumps', [])
    total = len(boundary) + len(large)
    if not total:
        return 0

    site = SiteSettings.get()

    def _row(e):
        return {
            'label': f"{e['student_name']} · {e['exam_title']}",
            'detail': f"{e['old_percentage']}% → {e['new_percentage']}% by {e['changed_by']}",
        }

    sent = 0
    for admin in User.objects.filter(role='super_admin', is_active=True):
        if get_frequency(admin, NotificationCategory.INTEGRITY_FLAG) != 'immediate':
            continue
        sent += int(send_notification(
            recipient=admin,
            category=NotificationCategory.INTEGRITY_FLAG,
            subject=f'{total} grading anomal{"y" if total == 1 else "ies"} to review — {site.platform_name}',
            template_base='integrity_flag_admin',
            context={
                'greeting': f'Hi {admin.first_name or admin.get_full_name()},',
                'flag_count': total,
                'boundary_crossings': [_row(e) for e in boundary[:10]],
                'large_edits': [_row(e) for e in large[:10]],
                'action_label': 'Review integrity flags',
                'action_url': f'{settings.FRONTEND_URL}/analytics/integrity',
            },
            related_object_type='integrity_scan', related_object_id=1,
            summary=f'{total} grading anomalies found',
            cooldown_days=INTEGRITY_COOLDOWN_DAYS,
        ))
    return sent


# ── Orchestrator: immediate alerts (management command entry point) ────

def run_analytics_alerts(classroom_id: int = None) -> dict:
    """
    Re-runs the same at-risk / risk-score / integrity detection the
    dashboard pages use, and emails anyone with an 'immediate' preference
    for what it finds — each function above handles its own per-recipient
    preference check and cooldown, so this just fans out over classrooms.
    Meant to be run periodically (e.g. daily) via `send_analytics_alerts`.
    """
    classrooms = Classroom.objects.filter(is_active=True)
    if classroom_id:
        classrooms = classrooms.filter(id=classroom_id)
    classrooms = list(classrooms)

    counts = {'at_risk': 0, 'risk_critical': 0, 'integrity_flag': 0}

    for classroom in classrooms:
        at_risk_rows = analytics_services.get_at_risk_students(classroom_ids=classroom.id, threshold=30.0)
        if at_risk_rows:
            profiles = {
                sp.id: sp for sp in StudentProfile.objects.select_related('user', 'classroom')
                .filter(id__in=[r['student_id'] for r in at_risk_rows])
            }
            for row in at_risk_rows:
                sp = profiles.get(row['student_id'])
                if sp:
                    counts['at_risk'] += notify_at_risk_student(row, sp)

        risk_data = analytics_services.get_classroom_risk_scores(classroom.id)
        critical_rows = [r for r in risk_data['students'] if r['risk_level'] == 'critical']
        if critical_rows:
            profiles = {
                sp.id: sp for sp in StudentProfile.objects.select_related('user', 'classroom')
                .filter(id__in=[r['student_id'] for r in critical_rows])
            }
            for row in critical_rows:
                sp = profiles.get(row['student_id'])
                if sp:
                    counts['risk_critical'] += notify_critical_risk(row, sp)

    integrity = analytics_services.get_integrity_flags()
    counts['integrity_flag'] = notify_integrity_flags(integrity)
    return counts


# ── Orchestrator: daily digest ──────────────────────────────────────────

def _digest_sections_for_parent(parent: User, since) -> list:
    links = list(ParentStudentLink.objects.filter(parent=parent).select_related('student', 'student__classroom', 'student__user'))
    students = {link.student_id: link.student for link in links}
    if not students:
        return []

    classroom_ids = list({sp.classroom_id for sp in students.values() if sp.classroom_id})
    sections = []

    at_risk_rows = analytics_services.get_at_risk_students(classroom_ids=classroom_ids, threshold=30.0) if classroom_ids else []
    at_risk_items = [
        {'emphasis': students[r['student_id']].full_name, 'emphasis_color': '#e11d48',
         'text': f"recent average {r['recent_average']}% in {students[r['student_id']].classroom}"}
        for r in at_risk_rows if r['student_id'] in students
    ]
    if at_risk_items:
        sections.append({'heading': 'At-risk', 'bg_color': '#fef2f2', 'border_color': '#fecdd3', 'items': at_risk_items})

    # "Recently published" is approximated via is_published + updated_at,
    # since publish doesn't stamp a dedicated timestamp — fine at this
    # scale (a handful of exams/day), documented rather than over-engineered.
    exam_items = []
    if classroom_ids:
        recent_exams = (Exam.objects.filter(classrooms__id__in=classroom_ids, is_published=True, updated_at__gte=since)
                         .distinct().prefetch_related('classrooms'))
        for exam in recent_exams:
            exam_classroom_ids = {c.id for c in exam.classrooms.all()}
            for sp in students.values():
                if sp.classroom_id in exam_classroom_ids:
                    score = ExamScore.objects.filter(exam=exam, student=sp, is_absent=False).first()
                    text = f'{exam.title} ({exam.get_exam_type_display()})'
                    if score:
                        text += f' — {sp.full_name} scored {score.percentage}%'
                    exam_items.append({'text': text})
    if exam_items:
        sections.append({'heading': 'Newly published exams', 'bg_color': '#eff6ff', 'border_color': '#bfdbfe', 'items': exam_items})

    return sections


def _digest_sections_for_staff(user: User, since) -> list:
    if user.role == 'teacher':
        classroom_ids = list(TeacherAssignment.objects.filter(teacher=user).values_list('classroom_id', flat=True).distinct())
    else:  # super_admin
        classroom_ids = list(Classroom.objects.filter(is_active=True).values_list('id', flat=True))
    if not classroom_ids:
        return []

    sections = []
    at_risk_rows = analytics_services.get_at_risk_students(classroom_ids=classroom_ids, threshold=30.0)
    if at_risk_rows:
        items = [
            {'emphasis': r['student_name'], 'emphasis_color': '#e11d48',
             'text': f"recent average {r['recent_average']}% ({r['classroom']})"}
            for r in at_risk_rows[:15]
        ]
        sections.append({'heading': f'At-risk students ({len(at_risk_rows)})', 'bg_color': '#fef2f2',
                          'border_color': '#fecdd3', 'items': items})

    if user.role == 'super_admin':
        integrity = analytics_services.get_integrity_flags()
        total = integrity['boundary_crossing_count'] + integrity['large_jump_count']
        if total:
            sections.append({
                'heading': f'Grading anomalies ({total})', 'bg_color': '#fffbeb', 'border_color': '#fde68a',
                'items': [{'text': f'{total} score edit(s) worth a second look — see the Integrity page.'}],
            })

    return sections


def send_daily_digest() -> int:
    """
    Entry point for `send_daily_digest`. Only emails users who actually
    have at least one category set to 'digest' — someone who's 'immediate'
    everywhere already got today's news as it happened, and someone who's
    'off' everywhere doesn't want email at all.
    """
    site = SiteSettings.get()
    since = timezone.now() - timedelta(hours=24)
    today_display = timezone.now().strftime('%A, %d %B %Y')
    digest_key = int(timezone.now().strftime('%Y%m%d'))  # dedupes same-day re-runs
    sent = 0

    for user in User.objects.filter(is_active=True, role__in=['parent', 'teacher', 'super_admin']):
        wants_digest = (
            get_frequency(user, NotificationCategory.AT_RISK) == 'digest'
            or get_frequency(user, NotificationCategory.EXAM_PUBLISHED) == 'digest'
        )
        if not wants_digest:
            continue

        sections = _digest_sections_for_parent(user, since) if user.role == 'parent' else _digest_sections_for_staff(user, since)
        item_count = sum(len(s['items']) for s in sections)

        sent += int(send_notification(
            recipient=user,
            category=NotificationCategory.DAILY_DIGEST,
            subject=f'Your daily summary — {today_display} · {site.platform_name}',
            template_base='daily_digest',
            context={
                'greeting': f'Hi {user.first_name or user.get_full_name()},',
                'today_display': today_display,
                'sections': sections,
                'action_label': 'Open dashboard',
                'action_url': f'{settings.FRONTEND_URL}/dashboard',
            },
            related_object_type='digest_day', related_object_id=digest_key,
            summary=f'{item_count} item(s)' if item_count else 'Nothing new today',
            cooldown_days=DIGEST_COOLDOWN_DAYS,
        ))

    return sent


# ── Ad-hoc analytics reports (command palette: `analytics send`) ───────────

ANALYTICS_REPORT_TYPES = ('overview', 'at-risk', 'class', 'student')


def _build_analytics_report_context(report_type: str, classroom=None, student=None, *, sender=None) -> dict | None:
    """Gathers the data + display context for one report type. Reuses the
    exact same analytics.services functions the dashboard pages call, so
    a report never drifts from what's shown on-screen. Returns None for
    an unknown type, a `class` report with no resolvable classroom, or a
    `student` report with no resolvable student.

    `sender` scopes the `overview` report's at-risk list down to a
    teacher's own classrooms. classroom/student-level access itself is
    already enforced by the caller (send_analytics_report) before this is
    ever reached, via the same scoping.py helpers every other analytics
    endpoint uses."""
    if report_type == 'student':
        if not student:
            return None
        summary = analytics_services.get_student_summary(student.id)
        if not summary:
            return None
        if not summary.get('total_exams'):
            return {
                'report_title': f"Student Report — {summary['student_name']}",
                'stats': [{'label': 'Exams recorded', 'value': '0'}],
                'at_risk_rows': [],
                'classroom_name': summary.get('classroom'),
                'recent_scores': [],
            }
        return {
            'report_title': f"Student Report — {summary['student_name']}",
            'stats': [
                {'label': 'Average score', 'value': f"{summary['average_percentage']}%"},
                {'label': 'Exams recorded', 'value': str(summary['total_exams'])},
                {'label': 'Pass rate', 'value': f"{summary['pass_rate']}%"},
                {'label': 'Trend', 'value': (summary['trend'] or '').replace('_', ' ').title() or '—'},
                {'label': 'Predicted NECTA grade', 'value': summary['predicted_necta_grade'] or '—'},
            ],
            'at_risk_rows': [],
            'classroom_name': summary.get('classroom'),
            'recent_scores': summary['recent_scores'][-10:],
        }

    if report_type == 'overview':
        # Teachers get an overview scoped to their own classrooms rather
        # than a platform-wide at-risk list they have no business seeing.
        if sender is not None and sender.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            classroom_ids = list(get_teacher_classrooms(sender).values_list('id', flat=True))
            at_risk = analytics_services.get_at_risk_students(classroom_ids=classroom_ids)
            total_students = StudentProfile.objects.filter(is_active=True, classroom_id__in=classroom_ids).count()
            total_classrooms = len(classroom_ids)
            title = 'My Classrooms — Analytics Overview'
        else:
            at_risk = analytics_services.get_at_risk_students()
            total_students = StudentProfile.objects.filter(is_active=True).count()
            total_classrooms = Classroom.objects.count()
            title = 'Platform Analytics Overview'
        return {
            'report_title': title,
            'stats': [
                {'label': 'Active students', 'value': str(total_students)},
                {'label': 'At-risk students', 'value': str(len(at_risk))},
                {'label': 'Classrooms tracked', 'value': str(total_classrooms)},
            ],
            'at_risk_rows': at_risk[:10],
            'classroom_name': None,
        }

    if report_type == 'at-risk':
        if classroom is not None:
            classroom_ids = classroom.id
            title = f'At-Risk Students — {classroom}'
            classroom_name = str(classroom)
        elif sender is not None and sender.role == 'teacher':
            from mathapi.apps.accounts.scoping import get_teacher_classrooms
            classroom_ids = list(get_teacher_classrooms(sender).values_list('id', flat=True))
            title = 'At-Risk Students — My Classrooms'
            classroom_name = None
        else:
            classroom_ids = None
            title = 'At-Risk Students — All Classrooms'
            classroom_name = None
        at_risk = analytics_services.get_at_risk_students(classroom_ids=classroom_ids)
        return {
            'report_title': title,
            'stats': [{'label': 'At-risk students', 'value': str(len(at_risk))}],
            'at_risk_rows': at_risk[:25],
            'classroom_name': classroom_name,
        }

    if report_type == 'class':
        if not classroom:
            return None
        data = analytics_services.get_class_analytics(classroom.id)
        if not data:
            return None
        avg = data.get('overall_average')
        return {
            'report_title': f'Class Performance — {classroom}',
            'stats': [
                {'label': 'Overall average', 'value': f"{avg}%" if avg is not None else '—'},
                {'label': 'Students ranked', 'value': str(len(data.get('student_rankings') or []))},
                {'label': 'At-risk in class', 'value': str(len(data.get('at_risk_students') or []))},
                {'label': 'Weak topics flagged', 'value': str(data.get('weak_topic_count', 0))},
            ],
            'at_risk_rows': [],
            'classroom_name': str(classroom),
        }

    return None


def send_analytics_report(*, sender, recipient_emails: list, report_type: str, classroom_id: int = None, student_id: int = None) -> dict:
    """
    Ad-hoc report send — powers the command palette's flagship
    `analytics send --to <emails> --report <type>` command. Deliberately
    separate from send_notification(): recipients here are raw email
    addresses (not required to be platform Users), there's no
    preference/cooldown check, and every attempt is logged to
    AnalyticsReportLog rather than NotificationLog.
    """
    from .models import AnalyticsReportLog

    if report_type not in ANALYTICS_REPORT_TYPES:
        return {'sent': False, 'error': f'Unknown report type "{report_type}". Choose one of: {", ".join(ANALYTICS_REPORT_TYPES)}.'}

    recipient_emails = [e.strip() for e in recipient_emails if e and e.strip()]
    if not recipient_emails:
        return {'sent': False, 'error': 'No valid recipient email addresses given.'}

    classroom = None
    if classroom_id:
        classroom = Classroom.objects.filter(id=classroom_id).first()
        if not classroom:
            return {'sent': False, 'error': f'Classroom {classroom_id} not found.'}

    student = None
    if student_id:
        student = StudentProfile.objects.filter(id=student_id).first()
        if not student:
            return {'sent': False, 'error': f'Student {student_id} not found.'}

    # A teacher may only email a report about a classroom/student they are
    # actually assigned to — mirrors the scoping every other analytics
    # endpoint enforces (see accounts.scoping / analytics._check_student_access).
    # super_admin is unrestricted; the view already blocks every other role.
    if sender.role == 'teacher':
        from mathapi.apps.accounts.scoping import assert_classroom_owned, get_teacher_classrooms
        if classroom is not None:
            assert_classroom_owned(sender, classroom.id)
        if student is not None and not get_teacher_classrooms(sender).filter(id=student.classroom_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have access to this student.')

    context = _build_analytics_report_context(report_type, classroom, student, sender=sender)
    if context is None:
        error = '"class" reports require a valid --classroom.' if report_type == 'class' else \
                '"student" reports require a valid --student.' if report_type == 'student' else \
                'Could not build that report.'
        return {'sent': False, 'error': error}

    site = SiteSettings.get()
    subject = f"{site.platform_name} — {context['report_title']} ({timezone.now().strftime('%d %b %Y')})"
    full_context = {
        **context,
        'subject': subject,
        'platform_name': site.platform_name,
        'logo_url': site.logo_url,
        'logo_letter': site.logo_letter,
        'footer_text': site.footer_text,
        'generated_at_display': timezone.now().strftime('%d %b %Y, %H:%M'),
        'triggered_by': sender.get_full_name() or sender.email,
    }

    try:
        html_body = render_to_string('notifications/analytics_report.html', full_context)
        text_body = render_to_string('notifications/analytics_report.txt', full_context)
        # BCC keeps the recipient list private from one another for a
        # broadcast like this; the sender gets a `to` copy for their records.
        msg = EmailMultiAlternatives(
            subject, text_body, settings.DEFAULT_FROM_EMAIL,
            to=[sender.email] if sender.email else [settings.DEFAULT_FROM_EMAIL],
            bcc=recipient_emails,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception as exc:
        AnalyticsReportLog.objects.create(
            sender=sender, recipients=recipient_emails, report_type=report_type,
            classroom=classroom, student=student, status=AnalyticsReportLog.Status.FAILED,
            error_message=str(exc)[:2000],
        )
        return {'sent': False, 'error': str(exc)}

    AnalyticsReportLog.objects.create(
        sender=sender, recipients=recipient_emails, report_type=report_type,
        classroom=classroom, student=student, status=AnalyticsReportLog.Status.SENT,
    )
    return {'sent': True, 'recipient_count': len(recipient_emails), 'report_title': context['report_title']}


# ── WhatsApp result delivery ────────────────────────────────────────────────

def _exam_result_whatsapp_body(student, exam, exam_score) -> str:
    result_line = (
        f'✅ PASSED (needed {exam.passing_score}/{exam.max_score})' if exam_score.passed
        else f'⚠️ Below pass mark (needed {exam.passing_score}/{exam.max_score})'
    )
    return (
        f'*MathPlatform* — Exam Result\n\n'
        f'Student: {student.full_name}\n'
        f'Exam: {exam.title} ({exam.get_term_display()}, {exam.academic_year})\n'
        f'Score: {exam_score.score}/{exam.max_score} ({exam_score.percentage}%) — Grade {exam_score.letter_grade}\n'
        f'{result_line}\n\n'
        f'This is an automated message from {student.classroom} — please contact the school for questions.'
    )


def send_whatsapp_exam_result(*, sender, student, exam) -> dict:
    """
    Sends a WhatsApp message with one student's result on one exam to
    every linked parent's phone number (falling back to the student's own
    phone if no parent is linked with one on file). Mirrors
    send_analytics_report's scoping and logging approach, just on a
    different channel.
    """
    from mathapi.apps.students.models import StudentProfile as _StudentProfile  # local import, avoids a cycle at module load
    from .whatsapp import send_whatsapp_message

    if sender.role == 'teacher':
        from mathapi.apps.accounts.scoping import get_teacher_classrooms
        if not get_teacher_classrooms(sender).filter(id=student.classroom_id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have access to this student.')

    if not exam.is_published:
        return {'sent': False, 'error': 'This exam has not been published yet.'}

    exam_score = ExamScore.objects.filter(exam=exam, student=student, is_absent=False).first()
    if not exam_score:
        return {'sent': False, 'error': 'No recorded score for this student on this exam.'}

    body = _exam_result_whatsapp_body(student, exam, exam_score)

    recipients = []
    parent_links = ParentStudentLink.objects.filter(student=student).select_related('parent')
    for link in parent_links:
        if link.parent.phone:
            recipients.append(link.parent)
    if not recipients and student.user_id and student.user.phone:
        recipients.append(student.user)

    if not recipients:
        return {'sent': False, 'error': 'No phone number on file for this student\'s parents or the student.'}

    sent_count = 0
    errors = []
    for recipient in recipients:
        ok, error = send_whatsapp_message(recipient.phone, body)
        NotificationLog.objects.create(
            recipient=recipient,
            category=NotificationCategory.EXAM_PUBLISHED,
            channel=NotificationLog.Channel.WHATSAPP,
            subject=f'Exam Result — {exam.title}',
            summary=f'{student.full_name}: {exam_score.score}/{exam.max_score} on {exam.title}',
            related_object_type='exam',
            related_object_id=exam.id,
            status=NotificationLog.Status.SENT if ok else NotificationLog.Status.FAILED,
            error_message='' if ok else error,
        )
        if ok:
            sent_count += 1
        else:
            errors.append(f'{recipient.get_full_name()}: {error}')

    return {
        'sent': sent_count > 0,
        'recipient_count': sent_count,
        'attempted_count': len(recipients),
        'errors': errors,
    }


# ── Trigger: tournament finalized ─────────────────────────────────────────

def notify_tournament_finalized(tournament, dossier: dict) -> int:
    """
    Called right after a tournament is finalized. Emails every entrant
    (student, if they have an 'immediate' preference) and every linked
    parent their own result — rank, score, movement vs. their own prior
    average, and any badges freshly earned in this tournament. Stream
    entries have no single student to notify and are skipped here; the
    classroom's teachers already see the outcome in-app.
    """
    site = SiteSettings.get()
    sent = 0
    newly_awarded = dossier.get('newly_awarded_badges', {})

    for result in dossier['results']:
        entry = result.entry
        if not entry.student_id:
            continue
        student = entry.student
        badge_names = [b.name for b in newly_awarded.get(student.id, [])]
        rank_display = f'#{result.rank} of {len(dossier["results"])}' if result.rank else 'Unranked'
        score_display = f'{result.score_percentage}%' if result.score_percentage is not None else 'Absent'
        score_color = '#16a34a' if (result.score_percentage or 0) >= 50 else '#e11d48'
        delta_display = f'{result.delta:+.1f} pts' if result.delta is not None else ''
        delta_color = '#16a34a' if (result.delta or 0) >= 0 else '#e11d48'
        first_name = student.user.first_name or student.full_name.split(' ')[0]

        base_context = {
            'tournament_title': tournament.title,
            'exam_title': tournament.exam.title,
            'classroom_name': str(student.classroom) if student.classroom else '',
            'is_champion': result.is_champion,
            'rank_display': rank_display,
            'score_display': score_display,
            'score_color': score_color,
            'delta_display': delta_display,
            'delta_color': delta_color,
            'badge_names': badge_names,
            'student_first_name': first_name,
            'action_label': 'View tournament',
            'action_url': f'{settings.FRONTEND_URL}/tournaments',
        }

        # The student themself
        if student.user.is_active and get_frequency(student.user, NotificationCategory.TOURNAMENT_RESULT) == 'immediate':
            sent += int(send_notification(
                recipient=student.user,
                category=NotificationCategory.TOURNAMENT_RESULT,
                subject=(f'You won {tournament.title}!' if result.is_champion
                         else f'Your result for {tournament.title} — {site.platform_name}'),
                template_base='tournament_result',
                context={**base_context, 'greeting': f'Hi {first_name},', 'is_own_result': True},
                related_object_type='tournament', related_object_id=tournament.id,
                summary=f'{student.full_name}: {rank_display} in "{tournament.title}"',
                cooldown_days=TOURNAMENT_RESULT_COOLDOWN_DAYS,
            ))

        # Linked parents
        links = ParentStudentLink.objects.filter(student=student).select_related('parent')
        for link in links:
            parent = link.parent
            if not parent.is_active or get_frequency(parent, NotificationCategory.TOURNAMENT_RESULT) != 'immediate':
                continue
            sent += int(send_notification(
                recipient=parent,
                category=NotificationCategory.TOURNAMENT_RESULT,
                subject=(f'{student.full_name} won {tournament.title}!' if result.is_champion
                         else f'{student.full_name}: tournament result — {site.platform_name}'),
                template_base='tournament_result',
                context={
                    **base_context,
                    'greeting': f'Hi {parent.first_name or parent.get_full_name()},',
                    'is_own_result': False,
                },
                related_object_type='tournament', related_object_id=tournament.id,
                summary=f'{student.full_name}: {rank_display} in "{tournament.title}"',
                cooldown_days=TOURNAMENT_RESULT_COOLDOWN_DAYS,
            ))

    return sent
