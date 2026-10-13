"""Outbound email helpers. SMTP login is read from backend/.env on each send."""

from __future__ import annotations

import logging

import environ
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger(__name__)


def _smtp_from_env() -> dict:
    """Read mailbox settings from disk so a running server picks up .env without a stale From address."""
    env = environ.Env()
    env.read_env(settings.BASE_DIR / ".env", overwrite=True)
    user = (env("EMAIL_HOST_USER", default="") or "").strip()
    password = env("EMAIL_HOST_PASSWORD", default="") or ""
    from_email = (env("DEFAULT_FROM_EMAIL", default="") or user).strip()
    return {
        "host": env("EMAIL_HOST", default="smtp.gmail.com"),
        "port": env.int("EMAIL_PORT", default=587),
        "username": user,
        "password": password,
        "use_tls": env.bool("EMAIL_USE_TLS", default=True),
        "from_email": from_email,
    }


def send_system_email(
    *,
    subject: str,
    message: str,
    recipients: list[str],
    html_message: str | None = None,
) -> bool:
    """
    Send from the Gmail account in backend/.env. Returns True on success.

    Failures are logged and return False so callers (invites, expense events) can continue.
    """
    recipients = [email.strip() for email in recipients if email and email.strip()]
    if not recipients:
        return False
    smtp = _smtp_from_env()
    if not smtp["username"] or not smtp["password"] or not smtp["from_email"]:
        logger.error("SMTP is not configured in backend/.env (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD).")
        return False
    try:
        connection = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=smtp["host"],
            port=smtp["port"],
            username=smtp["username"],
            password=smtp["password"],
            use_tls=smtp["use_tls"],
            fail_silently=False,
        )
        email = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=smtp["from_email"],
            to=recipients,
            connection=connection,
        )
        if html_message:
            email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
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
