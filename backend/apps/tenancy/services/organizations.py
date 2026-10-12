from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.access_control.models import AssignmentScope
from apps.access_control.services import sync_system_roles
from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError
from apps.core.validators import contrast_ratio
from apps.subscriptions.services import require_feature, start_subscription

from ..models import (
    OnboardingStatus,
    Organization,
    OrganizationBranding,
    OrganizationStatus,
)
from .invitations import create_invitation_record

MIN_TEXT_CONTRAST = 4.5

ORGANIZATION_SETTINGS_FIELDS = (
    "name",
    "legal_name",
    "industry",
    "currency",
    "timezone",
    "locale",
    "country",
    "tax_registration_number",
    "prices_include_tax",
    "contact_email",
    "contact_phone",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
)

BRANDING_FIELDS = (
    "display_name",
    "logo_url",
    "primary_color",
    "secondary_color",
    "background_color",
    "surface_color",
    "text_color",
)


@transaction.atomic
def onboard_organization(
    *,
    actor,
    name: str,
    slug: str,
    industry: str,
    currency: str,
    timezone_name: str,
    country: str,
    locale: str,
    plan,
    owner_email: str,
    request=None,
) -> tuple[Organization, str]:
    """Create a tenant with system roles, branding, a subscription and an owner invitation."""
    if Organization.objects.filter(slug=slug).exists():
        raise ConflictError("An organization with this slug already exists.")
    now = timezone.now()
    organization = Organization(
        name=name,
        slug=slug,
        industry=industry,
        currency=currency,
        timezone=timezone_name,
        country=country,
        locale=locale,
        status=OrganizationStatus.ACTIVE,
        onboarding_status=OnboardingStatus.IN_PROGRESS,
        activated_at=now,
    )
    organization.full_clean()
    organization.save()
    OrganizationBranding.objects.create(organization=organization, display_name=name)
    roles = sync_system_roles(organization)
    start_subscription(organization, plan)
    invitation, raw_token = create_invitation_record(
        organization=organization,
        email=owner_email,
        role_assignments=[{"role_id": str(roles["owner"].pk), "scope": AssignmentScope.TENANT}],
        branch_ids=[],
        is_owner=True,
        invited_by=actor,
    )
    record_event(
        action="platform.tenant_onboarded",
        actor=actor,
        organization=organization,
        target=organization,
        metadata={"slug": slug, "plan": plan.code, "owner_email": owner_email},
        request=request,
    )
    return organization, raw_token


_STATUS_TRANSITIONS = {
    OrganizationStatus.PENDING: {OrganizationStatus.ACTIVE, OrganizationStatus.DEACTIVATED},
    OrganizationStatus.ACTIVE: {OrganizationStatus.SUSPENDED, OrganizationStatus.DEACTIVATED},
    OrganizationStatus.SUSPENDED: {OrganizationStatus.ACTIVE, OrganizationStatus.DEACTIVATED},
    OrganizationStatus.DEACTIVATED: {OrganizationStatus.ACTIVE},
}


@transaction.atomic
def change_organization_status(
    *, actor, organization: Organization, status: str, reason: str, request=None
) -> Organization:
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if status not in _STATUS_TRANSITIONS[organization.status]:
        raise BusinessRuleViolation(
            f"An organization cannot move from {organization.status} to {status}."
        )
    previous = organization.status
    now = timezone.now()
    organization.status = status
    organization.status_reason = reason
    if status == OrganizationStatus.ACTIVE:
        organization.activated_at = now
    elif status == OrganizationStatus.SUSPENDED:
        organization.suspended_at = now
    elif status == OrganizationStatus.DEACTIVATED:
        organization.deactivated_at = now
    organization.save()
    record_event(
        action="platform.tenant_status_changed",
        actor=actor,
        organization=organization,
        target=organization,
        metadata={"from": previous, "to": status, "reason": reason},
        request=request,
    )
    return organization


@transaction.atomic
def update_organization_settings(ctx, data: dict, *, request=None) -> Organization:
    organization = Organization.objects.select_for_update().get(pk=ctx.organization.pk)
    changed = {}
    for field in ORGANIZATION_SETTINGS_FIELDS:
        if field in data and getattr(organization, field) != data[field]:
            changed[field] = [getattr(organization, field), data[field]]
            setattr(organization, field, data[field])
    if changed:
        organization.full_clean()
        organization.save()
        record_event(
            action="organization.settings_updated",
            actor=ctx.user,
            organization=organization,
            target=organization,
            metadata=changed,
            request=request,
        )
    return organization


@transaction.atomic
def update_branding(ctx, data: dict, *, request=None) -> OrganizationBranding:
    require_feature(ctx.entitlements, "custom_branding")
    branding, _ = OrganizationBranding.objects.select_for_update().get_or_create(
        organization=ctx.organization
    )
    changed = {}
    for field in BRANDING_FIELDS:
        if field in data and getattr(branding, field) != data[field]:
            changed[field] = [getattr(branding, field), data[field]]
            setattr(branding, field, data[field])
    branding.full_clean()
    for surface in ("background_color", "surface_color"):
        ratio = contrast_ratio(branding.text_color, getattr(branding, surface))
        if ratio < MIN_TEXT_CONTRAST:
            raise ValidationError(
                {
                    "text_color": [
                        f"Text contrast against {surface} is {ratio:.1f}:1; use 4.5:1 or more."
                    ]
                }
            )
    if changed:
        branding.save()
        record_event(
            action="organization.branding_updated",
            actor=ctx.user,
            organization=ctx.organization,
            target=branding,
            metadata=changed,
            request=request,
        )
    return branding
