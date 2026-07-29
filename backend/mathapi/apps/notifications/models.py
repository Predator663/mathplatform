from django.conf import settings
from django.db import models


class NotificationCategory(models.TextChoices):
    AT_RISK        = 'at_risk', 'Student At-Risk Alert'
    RISK_CRITICAL  = 'risk_critical', 'Critical Risk Score'
    EXAM_PUBLISHED = 'exam_published', 'Exam Published'
    INTEGRITY_FLAG = 'integrity_flag', 'Grade Integrity Flag'
    DAILY_DIGEST   = 'daily_digest', 'Daily Digest'
    TEST           = 'test', 'Test Email'


class NotificationFrequency(models.TextChoices):
    IMMEDIATE = 'immediate', 'Send immediately'
    DIGEST    = 'digest', 'Include in daily digest'
    OFF       = 'off', 'Turn off'


# Sensible per-role defaults, used whenever a user hasn't explicitly set a
# preference for a category (i.e. no NotificationPreference row exists yet).
# Parents default to digests for the high-volume categories (less inbox
# noise) but immediate for critical risk, since that one is meant to prompt
# same-day action. Teachers/admins get immediate alerts for what they can
# act on fastest and skip the categories that are someone else's job.
DEFAULT_FREQUENCY_BY_ROLE = {
    'parent': {
        'at_risk': 'digest', 'risk_critical': 'immediate',
        'exam_published': 'digest', 'integrity_flag': 'off',
    },
    'teacher': {
        'at_risk': 'immediate', 'risk_critical': 'immediate',
        'exam_published': 'off', 'integrity_flag': 'off',
    },
    'super_admin': {
        'at_risk': 'digest', 'risk_critical': 'immediate',
        'exam_published': 'off', 'integrity_flag': 'immediate',
    },
    'student': {
        'at_risk': 'off', 'risk_critical': 'off',
        'exam_published': 'digest', 'integrity_flag': 'off',
    },
}


class NotificationPreference(models.Model):
    """
    Per-user, per-category delivery override. A user with NO row for a
    category simply uses DEFAULT_FREQUENCY_BY_ROLE[user.role][category] —
    rows only exist for categories someone has explicitly changed, so
    onboarding a new user never requires seeding N rows per user.
    """
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='notification_preferences')
    category   = models.CharField(max_length=30, choices=NotificationCategory.choices)
    frequency  = models.CharField(max_length=10, choices=NotificationFrequency.choices,
                                   default=NotificationFrequency.IMMEDIATE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'
        unique_together = ['user', 'category']

    def __str__(self):
        return f'{self.user.email} · {self.category} · {self.frequency}'


class NotificationLog(models.Model):
    """
    Audit trail of every notification email attempted. Serves two purposes:

      1. Dedupe/cooldown source — before re-sending an "immediate" alert
         (e.g. the same student is still at-risk the next time the alert
         command runs), notifications.services checks for a recent SENT
         row for the same (recipient, category, related_object) so people
         aren't emailed the same flag every single run.
      2. In-app notification history — a read-only feed of what's been
         emailed to the current user, so it's visible even without opening
         their inbox (e.g. a "Notifications" page in the app).
    """
    class Status(models.TextChoices):
        SENT    = 'sent', 'Sent'
        FAILED  = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped (preference off)'

    recipient  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='notifications')
    category   = models.CharField(max_length=30, choices=NotificationCategory.choices)
    subject    = models.CharField(max_length=255)
    summary    = models.CharField(max_length=500, blank=True,
                                   help_text="One-line plain-text summary for the in-app list")

    # A loose pointer back to what this notification was about (a student,
    # exam, classroom...) rather than a real FK/GenericForeignKey, since the
    # subject varies per category and this table is read-only audit data —
    # never joined against, only filtered by type+id for the cooldown check.
    related_object_type = models.CharField(max_length=30, blank=True)
    related_object_id   = models.IntegerField(null=True, blank=True)

    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.SENT)
    error_message = models.TextField(blank=True)
    sent_at       = models.DateTimeField(auto_now_add=True)
    read_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notification_logs'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['recipient', 'sent_at']),
            models.Index(fields=['category', 'related_object_type', 'related_object_id', 'sent_at']),
        ]

    def __str__(self):
        return f'{self.category} → {self.recipient.email} ({self.status})'
