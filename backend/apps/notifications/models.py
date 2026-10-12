from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class NotificationType(models.TextChoices):
    EXPENSE_SUBMITTED = "EXPENSE_SUBMITTED", "Expense submitted"
    EXPENSE_APPROVED = "EXPENSE_APPROVED", "Expense approved"
    EXPENSE_REJECTED = "EXPENSE_REJECTED", "Expense rejected"
    EXPENSE_REMINDER = "EXPENSE_REMINDER", "Expense reminder"
    EXPENSE_PAID = "EXPENSE_PAID", "Expense paid"
    INVITATION = "INVITATION", "Invitation"
    GENERIC = "GENERIC", "Generic"


class Notification(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="notifications"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=32, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link_path = models.CharField(max_length=500, blank=True)
    expense_id = models.UUIDField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "user", "read_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class BrandNotificationSettings(TimeStampedModel):
    organization = models.OneToOneField(
        "tenancy.Organization",
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )
    primary_email = models.EmailField(blank=True)
    extra_recipient_emails = ArrayField(
        models.EmailField(), default=list, blank=True, size=20
    )
    reminder_intervals_hours = ArrayField(
        models.PositiveSmallIntegerField(), default=list, blank=True, size=10
    )
    reminders_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "brand notification settings"

    def resolved_primary_email(self) -> str:
        return (self.primary_email or self.organization.contact_email or "").strip()

    def recipient_emails(self) -> list[str]:
        emails: list[str] = []
        primary = self.resolved_primary_email()
        if primary:
            emails.append(primary)
        for email in self.extra_recipient_emails or []:
            cleaned = (email or "").strip().lower()
            if cleaned and cleaned not in {e.lower() for e in emails}:
                emails.append(cleaned)
        return emails

    def reminder_hours(self) -> list[int]:
        hours = list(self.reminder_intervals_hours or [])
        if not hours:
            return [24, 48]
        return sorted(set(int(h) for h in hours if h > 0))


class EmailDeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    SKIPPED = "SKIPPED", "Skipped"


class EmailDeliveryLog(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.CASCADE, related_name="email_delivery_logs"
    )
    expense = models.ForeignKey(
        "expenses.Expense",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    event = models.CharField(max_length=64)
    recipient = models.EmailField()
    interval_key = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=EmailDeliveryStatus.choices, default=EmailDeliveryStatus.PENDING
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "event", "status"]),
            models.Index(fields=["status", "updated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["expense", "event", "recipient", "interval_key"],
                condition=Q(expense__isnull=False),
                name="notifications_emaillog_expense_event_recipient_interval_uniq",
            ),
        ]
