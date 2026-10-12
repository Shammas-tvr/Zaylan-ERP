from datetime import datetime

from django.core.management.base import BaseCommand

from apps.expenses.services import generate_recurring_for_period


class Command(BaseCommand):
    help = "Generate pending recurring expense entries for the current (or given) billing period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--as-of",
            help="Date YYYY-MM-DD (defaults to today in the server timezone).",
        )

    def handle(self, *args, **options):
        as_of = None
        if options.get("as_of"):
            as_of = datetime.strptime(options["as_of"], "%Y-%m-%d").date()
        result = generate_recurring_for_period(as_of=as_of)
        self.stdout.write(
            self.style.SUCCESS(
                f"Period {result['period']}: created={result['created']} skipped={result['skipped']}"
            )
        )
