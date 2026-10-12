import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.access_control.services import grant_platform_role, sync_permission_catalog
from apps.subscriptions.services import ensure_default_plans


class Command(BaseCommand):
    help = (
        "Sync permission/feature catalogs, create default plans, and optionally create a platform "
        "super admin. The password is read from PLATFORM_ADMIN_PASSWORD or prompted."
    )

    def add_arguments(self, parser):
        parser.add_argument("--admin-email")
        parser.add_argument("--admin-name", default="Platform Admin")

    @transaction.atomic
    def handle(self, *args, admin_email=None, admin_name="Platform Admin", **options):
        sync_permission_catalog()
        ensure_default_plans()
        self.stdout.write(self.style.SUCCESS("Catalogs and default plans are ready."))
        if not admin_email:
            return

        User = get_user_model()
        user = User.objects.filter(email__iexact=admin_email).first()
        if user is None:
            password = os.environ.get("PLATFORM_ADMIN_PASSWORD") or getpass.getpass("Password: ")
            candidate = User(email=admin_email, full_name=admin_name)
            try:
                validate_password(password, candidate)
            except Exception as exc:
                raise CommandError("; ".join(getattr(exc, "messages", [str(exc)]))) from exc
            user = User.objects.create_user(
                email=admin_email, password=password, full_name=admin_name
            )
            self.stdout.write(f"Created user {user.email}.")
        grant_platform_role(user=user, role_key="platform_super_admin")
        self.stdout.write(self.style.SUCCESS(f"{user.email} is a platform super admin."))
