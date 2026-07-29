from django.core.management.base import BaseCommand, CommandError

from mathapi.apps.notifications import services


class Command(BaseCommand):
    help = (
        "Scans for students who are at-risk, have a critical composite risk score, "
        "or have grading anomalies flagged, and emails everyone with an 'immediate' "
        "notification preference. Safe to run repeatedly (e.g. daily via cron) — "
        "per-recipient cooldowns stop the same ongoing situation from re-emailing "
        "every run. Schedule this with whatever free cron mechanism you have "
        "available (Render Cron Jobs, an OS crontab, a GitHub Actions scheduled "
        "workflow hitting a protected endpoint, etc.) — e.g. once daily."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--classroom', type=int, default=None,
            help='Only scan this classroom ID (default: every active classroom).',
        )

    def handle(self, *args, **options):
        classroom_id = options['classroom']
        try:
            counts = services.run_analytics_alerts(classroom_id=classroom_id)
        except Exception as exc:
            raise CommandError(f'Alert run failed: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f"Sent {counts['at_risk']} at-risk alert(s), "
            f"{counts['risk_critical']} critical-risk alert(s), "
            f"{counts['integrity_flag']} integrity-flag alert(s)."
        ))
