from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel, UUIDModel


class Feature(UUIDModel):
    """Synchronized from ``catalog.py``."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    is_limit = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class Plan(TimeStampedModel):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    trial_days = models.PositiveIntegerField(default=14)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PlanEntitlement(UUIDModel):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="entitlements")
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT, related_name="+")
    enabled = models.BooleanField(default=True)
    # Only meaningful for limit features; null means unlimited.
    limit_value = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(0)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plan", "feature"], name="subscriptions_entitlement_unique"
            ),
        ]


class SubscriptionStatus(models.TextChoices):
    TRIALING = "TRIALING", "Trialing"
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past due"
    SUSPENDED = "SUSPENDED", "Suspended"
    CANCELLED = "CANCELLED", "Cancelled"


class OrganizationSubscription(TimeStampedModel):
    organization = models.OneToOneField(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="subscription"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=SubscriptionStatus.choices)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    # Reserved for a future billing provider integration.
    billing_provider = models.CharField(max_length=50, blank=True)
    external_customer_id = models.CharField(max_length=255, blank=True)
    external_subscription_id = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="TRIALING") | Q(trial_ends_at__isnull=False),
                name="subscriptions_trial_requires_end",
            ),
        ]
        indexes = [models.Index(fields=["status"])]
