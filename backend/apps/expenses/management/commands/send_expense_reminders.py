from django.core.management.base import BaseCommand

from apps.expenses.services import send_pending_reminders


class Command(BaseCommand):
    help = "Send reminder emails for expenses still awaiting Brand Admin approval."

    def handle(self, *args, **options):
        result = send_pending_reminders()
        self.stdout.write(
            self.style.SUCCESS(f"Reminders sent={result['sent']} skipped={result['skipped']}")
        )
