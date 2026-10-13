from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel
from apps.core.validators import (
    validate_country_code,
    validate_currency_code,
    validate_hex_color,
    validate_timezone,
)


class Industry(models.TextChoices):
    DESSERT_SHOP = "DESSERT_SHOP", "Dessert shop"
    BAKERY = "BAKERY", "Bakery"
    CAFE = "CAFE", "Cafe"
    RESTAURANT = "RESTAURANT", "Restaurant"
    RETAIL = "RETAIL", "Retail"
    OTHER = "OTHER", "Other"


class OrganizationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    DEACTIVATED = "DEACTIVATED", "Deactivated"


class OnboardingStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not started"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"


class Organization(TimeStampedModel):
    """The tenant boundary. Every tenant-owned record references an organization."""

    slug = models.SlugField(max_length=63, unique=True, validators=[MinLengthValidator(3)])
    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=200, blank=True)
    industry = models.CharField(max_length=32, choices=Industry.choices, default=Industry.OTHER)
    status = models.CharField(
        max_length=16, choices=OrganizationStatus.choices, default=OrganizationStatus.PENDING
    )
    status_reason = models.CharField(max_length=500, blank=True)

    currency = models.CharField(max_length=3, default="INR", validators=[validate_currency_code])
    timezone = models.CharField(
        max_length=64, default="Asia/Kolkata", validators=[validate_timezone]
    )
    locale = models.CharField(max_length=16, default="en-IN")
    country = models.CharField(max_length=2, default="IN", validators=[validate_country_code])
    tax_registration_number = models.CharField(max_length=32, blank=True)
    prices_include_tax = models.BooleanField(default=True)

    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    # Public brand entry URL, e.g. https://app.example/b/zaylan
    portal_url = models.URLField(max_length=500, blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=16, blank=True)

    onboarding_status = models.CharField(
        max_length=16, choices=OnboardingStatus.choices, default=OnboardingStatus.NOT_STARTED
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return self.name


class MembershipStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class OrganizationMembership(TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="memberships"
    )
    status = models.CharField(
        max_length=16, choices=MembershipStatus.choices, default=MembershipStatus.ACTIVE
    )
    is_owner = models.BooleanField(default=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="tenancy_membership_org_user_unique"
            ),
            # Target for composite foreign keys that keep related rows in the same tenant.
            models.UniqueConstraint(
                fields=["organization", "id"], name="tenancy_membership_org_id_unique"
            ),
        ]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.organization_id}"


class OrganizationBranding(TimeStampedModel):
    organization = models.OneToOneField(
        Organization, on_delete=models.PROTECT, related_name="branding"
    )
    display_name = models.CharField(max_length=150, blank=True)
    logo_url = models.URLField(blank=True)
    primary_color = models.CharField(
        max_length=7, default="#6B2E2E", validators=[validate_hex_color]
    )
    secondary_color = models.CharField(
        max_length=7, default="#B58A5A", validators=[validate_hex_color]
    )
    background_color = models.CharField(
        max_length=7, default="#F3E7D6", validators=[validate_hex_color]
    )
    surface_color = models.CharField(
        max_length=7, default="#FFFBF5", validators=[validate_hex_color]
    )
    text_color = models.CharField(max_length=7, default="#171717", validators=[validate_hex_color])


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    REVOKED = "REVOKED", "Revoked"


class OrganizationInvitation(TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="invitations"
    )
    email = models.EmailField(max_length=254)
    # SHA-256 of the single-use token; the raw token is shown only once at creation.
    token_hash = models.CharField(max_length=64, unique=True)
    # [{"role_id": "<uuid>", "scope": "TENANT" | "BRANCHES"}], revalidated on acceptance.
    role_assignments = models.JSONField(default=list)
    branch_ids = models.JSONField(default=list)
    is_owner = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16, choices=InvitationStatus.choices, default=InvitationStatus.PENDING
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                "organization",
                Lower("email"),
                condition=Q(status="PENDING"),
                name="tenancy_invitation_one_pending_per_email",
            ),
        ]
        indexes = [models.Index(fields=["organization", "status"])]
