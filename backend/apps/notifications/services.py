"""In-app notifications, brand email settings, and expense email delivery."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.core.validators import normalize_email

from .mail import send_invitation_email, send_system_email
from .models import (
    BrandNotificationSettings,
    EmailDeliveryLog,
    EmailDeliveryStatus,
    Notification,
    NotificationType,
)

logger = logging.getLogger(__name__)

MAX_EMAIL_ATTEMPTS = 5


def ensure_brand_notification_settings(organization) -> BrandNotificationSettings:
    settings_row, _ = BrandNotificationSettings.objects.get_or_create(
        organization=organization,
        defaults={
            "primary_email": organization.contact_email or "",
            "reminder_intervals_hours": [24, 48],
            "reminders_enabled": True,
        },
    )
    return settings_row


def get_or_create_settings(organization) -> BrandNotificationSettings:
    return ensure_brand_notification_settings(organization)


@transaction.atomic
def update_notification_settings(ctx, data: dict, *, request=None) -> BrandNotificationSettings:
    from apps.audit_logs.services import record_event

    row = BrandNotificationSettings.objects.select_for_update().get_or_create(
        organization=ctx.organization,
        defaults={"primary_email": ctx.organization.contact_email or ""},
    )[0]
    changed = {}
    if "primary_email" in data:
        value = normalize_email(data["primary_email"]) if data["primary_email"] else ""
        if row.primary_email != value:
            changed["primary_email"] = [row.primary_email, value]
            row.primary_email = value
    if "extra_recipient_emails" in data:
        emails = [normalize_email(e) for e in data["extra_recipient_emails"] if e]
        if list(row.extra_recipient_emails or []) != emails:
            changed["extra_recipient_emails"] = [list(row.extra_recipient_emails or []), emails]
            row.extra_recipient_emails = emails
    if "reminder_intervals_hours" in data:
        hours = sorted({int(h) for h in data["reminder_intervals_hours"] if int(h) > 0})
        if list(row.reminder_intervals_hours or []) != hours:
            changed["reminder_intervals_hours"] = [list(row.reminder_intervals_hours or []), hours]
            row.reminder_intervals_hours = hours
    if "reminders_enabled" in data and row.reminders_enabled != data["reminders_enabled"]:
        changed["reminders_enabled"] = [row.reminders_enabled, data["reminders_enabled"]]
        row.reminders_enabled = data["reminders_enabled"]
    if changed:
        row.save()
        record_event(
            action="organization.notification_settings_updated",
            actor=ctx.user,
            organization=ctx.organization,
            target=row,
            metadata=changed,
            request=request,
        )
    return row


def create_notification(
    *,
    organization,
    user,
    notification_type: str,
    title: str,
    body: str = "",
    link_path: str = "",
    expense_id=None,
) -> Notification:
    return Notification.objects.create(
        organization=organization,
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        link_path=link_path,
        expense_id=expense_id,
    )


def notify_users(
    *,
    organization,
    users,
    notification_type: str,
    title: str,
    body: str = "",
    link_path: str = "",
    expense_id=None,
) -> list[Notification]:
    seen = set()
    created = []
    for user in users:
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        created.append(
            create_notification(
                organization=organization,
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                link_path=link_path,
                expense_id=expense_id,
            )
        )
    return created


def mark_notification_read(ctx, notification: Notification) -> Notification:
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])
    return notification


def mark_all_notifications_read(ctx) -> int:
    now = timezone.now()
    return Notification.objects.filter(
        organization=ctx.organization, user=ctx.user, read_at__isnull=True
    ).update(read_at=now, updated_at=now)


def deliver_invitation(*, organization_name: str, email: str, invite_url: str, is_owner: bool) -> bool:
    return send_invitation_email(
        organization_name=organization_name,
        email=email,
        invite_url=invite_url,
        is_owner=is_owner,
    )


def _record_delivery(
    *,
    organization,
    expense,
    event: str,
    recipient: str,
    interval_key: str,
    ok: bool,
    error: str = "",
) -> EmailDeliveryLog:
    log, _ = EmailDeliveryLog.objects.get_or_create(
        expense=expense,
        event=event,
        recipient=recipient,
        interval_key=interval_key or "",
        defaults={
            "organization": organization,
            "status": EmailDeliveryStatus.PENDING,
        },
    )
    log.attempts = (log.attempts or 0) + 1
    if ok:
        log.status = EmailDeliveryStatus.SENT
        log.sent_at = timezone.now()
        log.last_error = ""
    else:
        log.status = EmailDeliveryStatus.FAILED
        log.last_error = (error or "send failed")[:2000]
    log.save()
    return log


def send_expense_email(
    *,
    organization,
    expense,
    event: str,
    recipients: list[str],
    subject: str,
    message: str,
    html_message: str | None = None,
    interval_key: str = "",
) -> list[EmailDeliveryLog]:
    logs = []
    for recipient in recipients:
        recipient = normalize_email(recipient)
        if not recipient:
            continue
        if expense is not None and EmailDeliveryLog.objects.filter(
            expense=expense,
            event=event,
            recipient=recipient,
            interval_key=interval_key or "",
            status=EmailDeliveryStatus.SENT,
        ).exists():
            continue
        try:
            ok = send_system_email(
                subject=subject, message=message, recipients=[recipient], html_message=html_message
            )
            logs.append(
                _record_delivery(
                    organization=organization,
                    expense=expense,
                    event=event,
                    recipient=recipient,
                    interval_key=interval_key,
                    ok=ok,
                    error="" if ok else "provider returned failure",
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("expense email failed")
            logs.append(
                _record_delivery(
                    organization=organization,
                    expense=expense,
                    event=event,
                    recipient=recipient,
                    interval_key=interval_key,
                    ok=False,
                    error=str(exc),
                )
            )
    return logs


def retry_failed_emails(*, max_attempts: int = MAX_EMAIL_ATTEMPTS) -> int:
    """Retry temporary delivery failures. Returns number of successful retries."""
    from django.conf import settings

    from apps.expenses.models import Expense, ExpenseStatus

    pending = EmailDeliveryLog.objects.filter(
        status=EmailDeliveryStatus.FAILED, attempts__lt=max_attempts
    ).select_related("expense", "organization")[:200]
    recovered = 0
    for log in pending:
        expense = log.expense
        if expense is not None and log.event.startswith("reminder"):
            if expense.status != ExpenseStatus.PENDING_APPROVAL:
                log.status = EmailDeliveryStatus.SKIPPED
                log.last_error = "expense no longer pending"
                log.save(update_fields=["status", "last_error", "updated_at"])
                continue
        subject = f"[Zaylan] Retry: {log.event}"
        message = (
            f"This is a retry for event {log.event} regarding brand {log.organization.name}.\n"
            f"Open the workspace: {settings.FRONTEND_URL.rstrip('/')}/expenses"
        )
        if expense is not None:
            message += f"\nExpense: {expense.pk}"
        ok = send_system_email(subject=subject, message=message, recipients=[log.recipient])
        log.attempts += 1
        if ok:
            log.status = EmailDeliveryStatus.SENT
            log.sent_at = timezone.now()
            log.last_error = ""
            recovered += 1
        else:
            log.last_error = "retry failed"
        log.save()
    return recovered


def brand_admin_users(organization):
    """Users with expenses.approve at tenant scope (Brand Admins / authorized admins)."""
    from apps.access_control.models import AssignmentScope, MembershipRoleAssignment
    from apps.tenancy.models import MembershipStatus

    membership_ids = (
        MembershipRoleAssignment.objects.filter(
            organization=organization,
            scope=AssignmentScope.TENANT,
            role__permissions__code="expenses.approve",
        )
        .values_list("membership_id", flat=True)
        .distinct()
    )
    from apps.tenancy.models import OrganizationMembership

    return [
        m.user
        for m in OrganizationMembership.objects.filter(
            organization=organization,
            status=MembershipStatus.ACTIVE,
            pk__in=membership_ids,
        ).select_related("user")
    ]
