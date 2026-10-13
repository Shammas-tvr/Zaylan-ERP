import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.access_control.models import AssignmentScope, MembershipRoleAssignment
from apps.access_control.services import sync_system_roles
from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError
from apps.core.validators import contrast_ratio, normalize_email
from apps.subscriptions.services import require_feature, start_subscription

from ..models import (
    MembershipStatus,
    OnboardingStatus,
    Organization,
    OrganizationBranding,
    OrganizationMembership,
    OrganizationStatus,
)

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


def build_portal_url(slug: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/b/{slug}"


def slugify_brand_name(name: str) -> str:
    """
    Meaningful portal slug from a brand name.
    One word → that word; two or more → first + last (Bariq Mens Fashions → bariq-fashions).
    """
    words = [w for w in re.split(r"[^a-z0-9]+", (name or "").strip().lower()) if w]
    if not words:
        return "brand"
    if len(words) == 1:
        slug = words[0]
    else:
        slug = f"{words[0]}-{words[-1]}"
    if len(slug) < 3:
        slug = f"{slug}-brand"[:63]
    return slug[:63]


def allocate_unique_slug(base: str, *, exclude_pk=None) -> str:
    """Return a unique organization slug, appending -2, -3, … when needed."""
    base = slugify_brand_name(base)[:63]
    if len(base) < 3:
        base = (base + "-brand")[:63]
    candidate = base
    n = 2
    while True:
        qs = Organization.objects.filter(slug=candidate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        suffix = f"-{n}"
        candidate = f"{base[: 63 - len(suffix)]}{suffix}"
        n += 1
        if n > 9999:
            raise ConflictError("Could not allocate a unique brand slug.")


@transaction.atomic
def onboard_organization(
    *,
    actor,
    name: str,
    slug: str = "",
    industry: str,
    currency: str,
    timezone_name: str,
    country: str,
    locale: str,
    plan,
    owner_email: str,
    owner_password: str,
    owner_full_name: str = "",
    request=None,
    legal_name: str = "",
    contact_email: str = "",
    contact_phone: str = "",
) -> Organization:
    """
    Create a brand and its Brand Admin account (email + password) in one step.
    No invitation URL is issued — Super Admin sets credentials directly.
    Slug is auto-derived from name when blank; explicit slugs must be unique.
    """
    raw_slug = (slug or "").strip().lower()
    if raw_slug:
        slug = raw_slug
        if Organization.objects.filter(slug=slug).exists():
            raise ConflictError("A brand with this slug already exists.")
    else:
        slug = allocate_unique_slug(name)

    owner_email = normalize_email(owner_email)
    if get_user_model().objects.filter(email__iexact=owner_email).exists():
        raise ConflictError("This email is already used. Brand Admin email must be unique.")
    if Organization.objects.filter(contact_email__iexact=owner_email).exists():
        raise ConflictError("This email is already linked to another brand.")

    validate_password(owner_password)

    now = timezone.now()
    organization = Organization(
        name=name,
        slug=slug,
        industry=industry,
        currency=currency,
        timezone=timezone_name,
        country=country,
        locale=locale,
        legal_name=legal_name or "",
        contact_email=contact_email or owner_email,
        contact_phone=contact_phone or "",
        portal_url=build_portal_url(slug),
        status=OrganizationStatus.ACTIVE,
        onboarding_status=OnboardingStatus.COMPLETED,
        activated_at=now,
    )
    organization.full_clean()
    organization.save()
    OrganizationBranding.objects.create(organization=organization, display_name=name)
    from apps.notifications.services import ensure_brand_notification_settings

    ensure_brand_notification_settings(organization)
    from apps.inventory.services import ensure_brand_locations

    ensure_brand_locations(organization)
    roles = sync_system_roles(organization)
    start_subscription(organization, plan)

    User = get_user_model()
    owner = User.objects.create_user(
        email=owner_email,
        password=owner_password,
        full_name=(owner_full_name or owner_email.split("@")[0]).strip()[:150],
    )
    membership = OrganizationMembership.objects.create(
        organization=organization,
        user=owner,
        status=MembershipStatus.ACTIVE,
        is_owner=True,
    )
    MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=membership,
        role=roles["owner"],
        scope=AssignmentScope.TENANT,
        assigned_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    record_event(
        action="platform.tenant_onboarded",
        actor=actor,
        organization=organization,
        target=organization,
        metadata={"slug": slug, "plan": plan.code, "owner_email": owner_email},
        request=request,
    )
    return organization


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
def update_platform_brand(
    *,
    actor,
    organization: Organization,
    data: dict,
    request=None,
) -> Organization:
    """Super Admin edit of brand profile fields (name, slug, industry, contact)."""
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    changed = {}
    for field in ("name", "legal_name", "industry", "contact_phone"):
        if field not in data:
            continue
        value = data[field]
        if getattr(organization, field) != value:
            changed[field] = [getattr(organization, field), value]
            setattr(organization, field, value)
    if "owner_email" in data and data["owner_email"]:
        owner_email = normalize_email(data["owner_email"])
        membership = (
            organization.memberships.filter(is_owner=True)
            .select_related("user")
            .first()
        )
        if membership is None:
            raise ConflictError("This brand has no Brand Admin to update.")
        owner = membership.user
        if owner.email != owner_email:
            User = get_user_model()
            if User.objects.filter(email__iexact=owner_email).exclude(pk=owner.pk).exists():
                raise ConflictError("This email is already used. Brand Admin email must be unique.")
            if (
                Organization.objects.filter(contact_email__iexact=owner_email)
                .exclude(pk=organization.pk)
                .exists()
            ):
                raise ConflictError("This email is already linked to another brand.")
            changed["owner_email"] = [owner.email, owner_email]
            owner.email = owner_email
            owner.save(update_fields=["email"])
            organization.contact_email = owner_email
    if "slug" in data and data["slug"] and data["slug"] != organization.slug:
        new_slug = data["slug"].strip().lower()
        if Organization.objects.filter(slug=new_slug).exclude(pk=organization.pk).exists():
            raise ConflictError("A brand with this slug already exists.")
        changed["slug"] = [organization.slug, new_slug]
        organization.slug = new_slug
        organization.portal_url = build_portal_url(new_slug)
        changed["portal_url"] = organization.portal_url
    if changed:
        organization.full_clean()
        organization.save()
        record_event(
            action="platform.tenant_updated",
            actor=actor,
            organization=organization,
            target=organization,
            metadata=changed,
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
    if "slug" in data and data["slug"] and data["slug"] != organization.slug:
        new_slug = data["slug"].strip().lower()
        if Organization.objects.filter(slug=new_slug).exclude(pk=organization.pk).exists():
            raise ConflictError("A brand with this slug already exists.")
        changed["slug"] = [organization.slug, new_slug]
        organization.slug = new_slug
        organization.portal_url = build_portal_url(new_slug)
        changed["portal_url"] = organization.portal_url
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
