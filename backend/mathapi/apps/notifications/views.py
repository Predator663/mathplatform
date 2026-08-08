from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NotificationPreference, NotificationLog, NotificationCategory, DEFAULT_FREQUENCY_BY_ROLE
from .serializers import (
    NotificationPreferenceItemSerializer, NotificationPreferenceUpdateSerializer, NotificationLogSerializer,
)
from . import services


class NotificationPreferenceView(APIView):
    """
    GET  → every category with the CURRENT user's effective frequency
           (their own override if one exists, otherwise their role default).
    PATCH → upsert one or more {category, frequency} overrides in one call.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        overrides = {p.category: p.frequency for p in NotificationPreference.objects.filter(user=user)}
        role_defaults = DEFAULT_FREQUENCY_BY_ROLE.get(user.role, {})

        rows = []
        for category in NotificationCategory:
            if category == NotificationCategory.DAILY_DIGEST or category == NotificationCategory.TEST:
                continue  # not directly toggleable — digest inclusion is implied by the other categories
            frequency = overrides.get(category.value, role_defaults.get(category.value, 'immediate'))
            rows.append({
                'category': category.value,
                'category_label': category.label,
                'frequency': frequency,
                'is_default': category.value not in overrides,
            })
        return Response(NotificationPreferenceItemSerializer(rows, many=True).data)

    def patch(self, request):
        updates = request.data if isinstance(request.data, list) else [request.data]
        serializer = NotificationPreferenceUpdateSerializer(data=updates, many=True)
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data:
            NotificationPreference.objects.update_or_create(
                user=request.user, category=item['category'],
                defaults={'frequency': item['frequency']},
            )
        return self.get(request)


class NotificationLogListView(generics.ListAPIView):
    """Paginated in-app history of notifications sent to the current user, most recent first."""
    serializer_class = NotificationLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = NotificationLog.objects.filter(recipient=self.request.user, status=NotificationLog.Status.SENT)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        unread_only = self.request.query_params.get('unread_only')
        if unread_only in ('1', 'true', 'True'):
            qs = qs.filter(read_at__isnull=True)
        return qs


class NotificationUnreadCountView(APIView):
    """Lightweight endpoint for a notification-bell badge count."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = NotificationLog.objects.filter(
            recipient=request.user, status=NotificationLog.Status.SENT, read_at__isnull=True,
        ).count()
        return Response({'unread_count': count})


class NotificationMarkReadView(APIView):
    """POST {} → mark all as read. POST {'id': 5} → mark just that one."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        qs = NotificationLog.objects.filter(recipient=request.user, read_at__isnull=True)
        log_id = request.data.get('id')
        if log_id:
            qs = qs.filter(id=log_id)
        updated = qs.update(read_at=timezone.now())
        return Response({'marked_read': updated})


class _CronTriggerView(APIView):
    """
    Base for HTTP-triggerable versions of the management commands, meant to
    be called by a free EXTERNAL scheduler (a GitHub Actions workflow on a
    cron schedule, or a free pinger like cron-job.org) rather than a paid
    Render Cron Job / Background Worker. Auth is a shared secret header
    rather than a login, since the caller is a script, not a person.

    If CRON_SECRET isn't set in the environment, this endpoint refuses to
    run at all — safer default than "open to anyone" for an endpoint that
    sends real emails.
    """
    permission_classes = [permissions.AllowAny]

    def _check_secret(self, request):
        from django.conf import settings
        expected = getattr(settings, 'CRON_SECRET', '')
        if not expected:
            return Response(
                {'detail': 'CRON_SECRET is not configured on the server — refusing to run.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        provided = request.headers.get('X-Cron-Secret', '')
        if provided != expected:
            return Response({'detail': 'Invalid or missing X-Cron-Secret header.'}, status=status.HTTP_403_FORBIDDEN)
        return None


class RunAnalyticsAlertsView(_CronTriggerView):
    """POST, with header X-Cron-Secret: <CRON_SECRET> → runs the same scan as `manage.py send_analytics_alerts`."""

    def post(self, request):
        denied = self._check_secret(request)
        if denied:
            return denied
        counts = services.run_analytics_alerts(classroom_id=request.data.get('classroom_id'))
        return Response(counts)


class RunDailyDigestView(_CronTriggerView):
    """POST, with header X-Cron-Secret: <CRON_SECRET> → runs the same job as `manage.py send_daily_digest`."""

    def post(self, request):
        denied = self._check_secret(request)
        if denied:
            return denied
        sent = services.send_daily_digest()
        return Response({'sent': sent})


class TestEmailView(APIView):
    """
    Admin-only: sends a test email to the current admin's own address to
    confirm SMTP delivery is actually configured before relying on it —
    much faster feedback than waiting for the first real alert to (maybe)
    silently fail.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role != 'super_admin':
            return Response({'detail': 'Only administrators can send a test email.'}, status=status.HTTP_403_FORBIDDEN)
        if not request.user.email:
            return Response({'detail': 'Your account has no email address on file.'}, status=status.HTTP_400_BAD_REQUEST)

        ok = services.send_test_email(
            recipient=request.user,
            triggered_by=request.user.get_full_name() or request.user.email,
        )
        if ok:
            return Response({'detail': f'Test email sent to {request.user.email}.'})

        # Admin-only endpoint, so it's safe (and much more useful) to show
        # the actual SMTP exception rather than a generic failure message.
        last_log = (NotificationLog.objects.filter(recipient=request.user, category=NotificationCategory.TEST)
                    .order_by('-sent_at').first())
        error_detail = last_log.error_message if last_log and last_log.error_message else 'Unknown error — check server logs.'
        return Response(
            {'detail': f'Sending failed: {error_detail}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


class SendAnalyticsReportView(APIView):
    """
    Teacher/admin: emails an analytics report (overview / at-risk / class
    performance) to an arbitrary list of email addresses — not required
    to be platform users. Powers the command palette's `analytics send`
    command, but is a plain REST endpoint so it's usable from anywhere.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.role not in ('teacher', 'super_admin'):
            return Response({'detail': 'Only teachers and administrators can send analytics reports.'}, status=status.HTTP_403_FORBIDDEN)

        recipients = request.data.get('recipients')
        report_type = request.data.get('report_type', 'overview')
        classroom_id = request.data.get('classroom_id')
        student_id = request.data.get('student_id')

        if not isinstance(recipients, list) or not recipients:
            return Response({'detail': 'recipients must be a non-empty list of email addresses.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        invalid = []
        for addr in recipients:
            try:
                validate_email((addr or '').strip())
            except DjangoValidationError:
                invalid.append(addr)
        if invalid:
            return Response({'detail': f'Invalid email address(es): {", ".join(map(str, invalid))}'}, status=status.HTTP_400_BAD_REQUEST)

        result = services.send_analytics_report(
            sender=request.user,
            recipient_emails=recipients,
            report_type=report_type,
            classroom_id=classroom_id,
            student_id=student_id,
        )
        if result.get('sent'):
            return Response(result)
        return Response({'detail': result.get('error', 'Failed to send report.')}, status=status.HTTP_400_BAD_REQUEST)


class PingView(APIView):
    """Cheap round-trip endpoint for the command palette's `ping` command."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'pong': True, 'server_time': timezone.now().isoformat()})


class SystemStatusView(APIView):
    """
    Admin-only health snapshot for the command palette's `system status`
    command: DB reachability, whether SMTP looks configured (vs. still
    the placeholder from .env.example), and a couple of headline counts.
    Doesn't send a real test email — that's what `notifications test` is for.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'super_admin':
            return Response({'detail': 'Administrators only.'}, status=status.HTTP_403_FORBIDDEN)

        from django.conf import settings as dj_settings
        from django.db import connection
        from django.contrib.auth import get_user_model
        from mathapi.apps.students.models import StudentProfile

        checks = []

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            checks.append({'name': 'database', 'ok': True, 'detail': connection.vendor})
        except Exception as exc:
            checks.append({'name': 'database', 'ok': False, 'detail': str(exc)[:200]})

        email_host_user = getattr(dj_settings, 'EMAIL_HOST_USER', '') or ''
        placeholder_markers = ('change-me', 'example', 'your-email', 'youremail')
        email_configured = bool(email_host_user) and not any(m in email_host_user.lower() for m in placeholder_markers)
        checks.append({
            'name': 'smtp_config', 'ok': email_configured,
            'detail': email_host_user if email_configured else 'not configured (placeholder in .env)',
        })

        recent_failures = NotificationLog.objects.filter(status=NotificationLog.Status.FAILED).count()
        checks.append({
            'name': 'notification_failures', 'ok': recent_failures == 0,
            'detail': f'{recent_failures} failed send(s) logged',
        })

        User = get_user_model()
        checks.append({'name': 'students', 'ok': True, 'detail': f'{StudentProfile.objects.filter(is_active=True).count()} active records'})
        checks.append({'name': 'accounts', 'ok': True, 'detail': f'{User.objects.filter(is_active=True).count()} active accounts'})
        checks.append({'name': 'debug_mode', 'ok': not dj_settings.DEBUG, 'detail': 'ON — should be OFF in production' if dj_settings.DEBUG else 'off'})

        return Response({'checks': checks, 'server_time': timezone.now().isoformat()})
