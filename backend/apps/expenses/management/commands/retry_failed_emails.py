from django.core.management.base import BaseCommand

from apps.notifications.services import retry_failed_emails


class Command(BaseCommand):
    help = "Retry temporary email delivery failures (capped attempts)."

    def add_arguments(self, parser):
        parser.add_argument("--max-attempts", type=int, default=5)

    def handle(self, *args, **options):
        recovered = retry_failed_emails(max_attempts=options["max_attempts"])
        self.stdout.write(self.style.SUCCESS(f"Recovered deliveries: {recovered}"))
