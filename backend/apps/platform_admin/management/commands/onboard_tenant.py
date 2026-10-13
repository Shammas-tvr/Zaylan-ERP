from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions.models import Plan
from apps.subscriptions.services import ensure_default_plans
from apps.tenancy.models import Industry
from apps.tenancy.services.organizations import onboard_organization


class Command(BaseCommand):
    help = "Onboard a brand and create its Brand Admin account (email + password)."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--slug", required=True)
        parser.add_argument("--owner-email", required=True)
        parser.add_argument("--owner-password", required=True)
        parser.add_argument("--owner-name", default="")
        parser.add_argument("--industry", default=Industry.OTHER, choices=Industry.values)
        parser.add_argument("--plan", default="growth")
        parser.add_argument("--currency", default="INR")
        parser.add_argument("--timezone", default="Asia/Kolkata")
        parser.add_argument("--country", default="IN")
        parser.add_argument("--locale", default="en-IN")
        parser.add_argument("--legal-name", default="")
        parser.add_argument("--contact-phone", default="")

    def handle(self, *args, **opts):
        ensure_default_plans()
        plan = Plan.objects.filter(code=opts["plan"], is_active=True).first()
        if plan is None:
            raise CommandError(f"Unknown or inactive plan '{opts['plan']}'.")
        organization = onboard_organization(
            actor=None,
            name=opts["name"],
            slug=opts["slug"],
            industry=opts["industry"],
            currency=opts["currency"],
            timezone_name=opts["timezone"],
            country=opts["country"],
            locale=opts["locale"],
            plan=plan,
            owner_email=opts["owner_email"],
            owner_password=opts["owner_password"],
            owner_full_name=opts["owner_name"],
            legal_name=opts["legal_name"],
            contact_email=opts["owner_email"],
            contact_phone=opts["contact_phone"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Onboarded brand {organization.name} ({organization.slug}).")
        )
        self.stdout.write(f"Brand Admin email: {opts['owner_email']}")
        self.stdout.write(f"Brand portal URL: {organization.portal_url}")
