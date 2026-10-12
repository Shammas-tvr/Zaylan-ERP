"""Outbound email helpers. Secrets come from environment-backed Django settings only."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_system_email(
    *,
    subject: str,
    message: str,
    recipients: list[str],
    html_message: str | None = None,
) -> bool:
    """
    Send from the configured system sender. Returns True on success.

    Failures are logged and return False so callers (invites, expense events) can continue.
    """
    recipients = [email.strip() for email in recipients if email and email.strip()]
    if not recipients:
        return False
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@zaylan.local"
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send email to %s subject=%s", recipients, subject)
        return False


def send_invitation_email(*, organization_name: str, email: str, invite_url: str, is_owner: bool) -> bool:
    role = "Brand Admin" if is_owner else "team member"
    subject = f"You're invited to {organization_name} on Zaylan"
    message = (
        f"You have been invited as a {role} for {organization_name} on Zaylan.\n\n"
        f"Accept your invitation (single-use, expires soon):\n{invite_url}\n\n"
        "If you did not expect this email, you can ignore it."
    )
    html = (
        f"<p>You have been invited as a <strong>{role}</strong> for "
        f"<strong>{organization_name}</strong> on Zaylan.</p>"
        f'<p><a href="{invite_url}">Accept your invitation</a></p>'
        "<p>This link is single-use and expires soon. "
        "If you did not expect this email, you can ignore it.</p>"
    )
    return send_system_email(subject=subject, message=message, recipients=[email], html_message=html)
