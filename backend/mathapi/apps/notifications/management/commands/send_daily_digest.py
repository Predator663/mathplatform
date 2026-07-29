from django.core.management.base import BaseCommand, CommandError

from mathapi.apps.notifications import services


class Command(BaseCommand):
    help = (
        "Sends the daily digest email to every parent/teacher/admin who has at "
        "least one notification category set to 'digest' instead of 'immediate'. "
        "Meant to run once per day (e.g. early morning) via whatever free cron "
        "mechanism you have available — Render Cron Jobs, an OS crontab, etc."
    )

    def handle(self, *args, **options):
        try:
            sent = services.send_daily_digest()
        except Exception as exc:
            raise CommandError(f'Digest run failed: {exc}')

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} daily digest email(s).'))
