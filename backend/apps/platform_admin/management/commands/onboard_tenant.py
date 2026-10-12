from django.core.management.base import BaseCommand, CommandError

from apps.subscriptions.models import Plan
from apps.subscriptions.services import ensure_default_plans
from apps.tenancy.models import Industry
from apps.tenancy.services.invitations import invitation_url
from apps.tenancy.services.organizations import onboard_organization


class Command(BaseCommand):
    help = "Onboard a tenant and print the single-use owner invitation link."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--slug", required=True)
        parser.add_argument("--owner-email", required=True)
        parser.add_argument("--industry", default=Industry.OTHER, choices=Industry.values)
        parser.add_argument("--plan", default="growth")
        parser.add_argument("--currency", default="INR")
        parser.add_argument("--timezone", default="Asia/Kolkata")
        parser.add_argument("--country", default="IN")
        parser.add_argument("--locale", default="en-IN")

    def handle(self, *args, **opts):
        ensure_default_plans()
        plan = Plan.objects.filter(code=opts["plan"], is_active=True).first()
        if plan is None:
            raise CommandError(f"Unknown or inactive plan '{opts['plan']}'.")
        organization, raw_token = onboard_organization(
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
        )
        self.stdout.write(
            self.style.SUCCESS(f"Onboarded {organization.name} ({organization.slug}).")
        )
        self.stdout.write(f"Owner invitation link (single use): {invitation_url(raw_token)}")
