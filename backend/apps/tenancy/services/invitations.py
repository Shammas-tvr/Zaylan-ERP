import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError
from apps.core.validators import normalize_email

from ..models import (
    InvitationStatus,
    MembershipStatus,
    OnboardingStatus,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationStatus,
)

INVALID_INVITATION = "This invitation is invalid or has expired."


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def invitation_url(raw_token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/invitations/accept#token={raw_token}"


def create_invitation_record(
    *,
    organization,
    email: str,
    role_assignments: list[dict],
    branch_ids: list[str],
    is_owner: bool,
    invited_by,
) -> tuple[OrganizationInvitation, str]:
    raw_token = secrets.token_urlsafe(32)
    try:
        with transaction.atomic():
            invitation = OrganizationInvitation.objects.create(
                organization=organization,
                email=normalize_email(email),
                token_hash=hash_token(raw_token),
                role_assignments=role_assignments,
                branch_ids=[str(b) for b in branch_ids],
                is_owner=is_owner,
                invited_by=invited_by,
                expires_at=timezone.now() + timedelta(hours=settings.INVITATION_TTL_HOURS),
            )
    except IntegrityError as exc:
        raise ConflictError("A pending invitation already exists for this email.") from exc
    return invitation, raw_token


@transaction.atomic
def invite_member(
    ctx, *, email: str, assignments: list[dict], branches: list, request=None
) -> tuple[OrganizationInvitation, str]:
    """``assignments`` is ``[{"role": Role, "scope": str}]``; ``branches`` are Branch objects."""
    from apps.access_control.services import ensure_can_grant, role_permission_codes
    from apps.subscriptions.services import enforce_limit, organization_usage

    email = normalize_email(email)
    if OrganizationMembership.objects.filter(
        organization=ctx.organization, user__email=email
    ).exists():
        raise ConflictError("This person is already a member of the organization.")
    usage = organization_usage(ctx.organization)
    enforce_limit(ctx.entitlements, "members", usage["members"] + usage["pending_invitations"])
    ensure_can_grant(ctx, role_permission_codes(item["role"].pk for item in assignments))

    OrganizationInvitation.objects.filter(
        organization=ctx.organization,
        email=email,
        status=InvitationStatus.PENDING,
        expires_at__lte=timezone.now(),
    ).update(status=InvitationStatus.REVOKED, revoked_at=timezone.now())

    invitation, raw_token = create_invitation_record(
        organization=ctx.organization,
        email=email,
        role_assignments=[
            {"role_id": str(item["role"].pk), "scope": item["scope"]} for item in assignments
        ],
        branch_ids=[branch.pk for branch in branches],
        is_owner=False,
        invited_by=ctx.user,
    )
    record_event(
        action="members.invited",
        actor=ctx.user,
        organization=ctx.organization,
        target=invitation,
        metadata={
            "email": email,
            "roles": [item["role"].name for item in assignments],
            "branches": [branch.code for branch in branches],
        },
        request=request,
    )
    return invitation, raw_token


@transaction.atomic
def revoke_invitation(ctx, invitation: OrganizationInvitation, *, request=None) -> None:
    invitation = OrganizationInvitation.objects.select_for_update().get(
        pk=invitation.pk, organization=ctx.organization
    )
    if invitation.status != InvitationStatus.PENDING:
        raise BusinessRuleViolation("Only pending invitations can be revoked.")
    if invitation.is_owner:
        raise BusinessRuleViolation("The owner invitation can only be managed by the platform.")
    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["status", "revoked_at", "updated_at"])
    record_event(
        action="members.invitation_revoked",
        actor=ctx.user,
        organization=ctx.organization,
        target=invitation,
        metadata={"email": invitation.email},
        request=request,
    )


def find_pending_invitation(raw_token: str, *, for_update: bool = False):
    queryset = OrganizationInvitation.objects.select_related("organization")
    if for_update:
        queryset = queryset.select_for_update()
    try:
        invitation = queryset.get(token_hash=hash_token(raw_token or ""))
    except OrganizationInvitation.DoesNotExist:
        return None
    if (
        invitation.status != InvitationStatus.PENDING
        or invitation.expires_at <= timezone.now()
        or invitation.organization.status != OrganizationStatus.ACTIVE
    ):
        return None
    return invitation


@transaction.atomic
def accept_invitation(
    raw_token: str,
    *,
    authenticated_user=None,
    full_name: str = "",
    password: str = "",
    request=None,
):
    """Returns ``(membership, user, created_user)``. Tokens are single use."""
    from apps.access_control.models import AssignmentScope, MembershipRoleAssignment, Role
    from apps.branches.models import Branch, MembershipBranchAccess
    from apps.subscriptions.services import enforce_limit, get_entitlements

    invitation = find_pending_invitation(raw_token, for_update=True)
    if invitation is None:
        raise BusinessRuleViolation(INVALID_INVITATION, code="invitation_invalid")
    organization = invitation.organization
    User = get_user_model()

    user = User.objects.filter(email__iexact=invitation.email).first()
    created_user = False
    if user is not None:
        if authenticated_user is None or authenticated_user.pk != user.pk:
            raise BusinessRuleViolation(
                "Sign in with the invited email address to accept this invitation.",
                code="invitation_requires_login",
            )
    else:
        if authenticated_user is not None:
            raise BusinessRuleViolation(
                "This invitation was sent to a different email address.",
                code="invitation_email_mismatch",
            )
        if not full_name.strip():
            raise ValidationError({"full_name": ["Enter your name."]})
        candidate = User(email=invitation.email, full_name=full_name.strip())
        validate_password(password, candidate)
        user = User.objects.create_user(
            email=invitation.email, password=password, full_name=full_name.strip()
        )
        created_user = True

    if not invitation.is_owner:
        active_members = organization.memberships.filter(status=MembershipStatus.ACTIVE).count()
        enforce_limit(
            get_entitlements(getattr(organization, "subscription", None)), "members", active_members
        )

    membership, created = OrganizationMembership.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={"is_owner": invitation.is_owner, "invited_by": invitation.invited_by},
    )
    if not created:
        if membership.status == MembershipStatus.ACTIVE:
            raise ConflictError("You are already a member of this organization.")
        membership.status = MembershipStatus.ACTIVE
        membership.is_owner = membership.is_owner or invitation.is_owner
        membership.save(update_fields=["status", "is_owner", "updated_at"])

    # Revalidate everything stored on the invitation against the organization at acceptance time.
    role_scopes = {
        str(item.get("role_id")): item.get("scope")
        for item in invitation.role_assignments
        if item.get("scope") in AssignmentScope.values
    }
    roles = Role.objects.filter(organization=organization, pk__in=list(role_scopes))
    existing_roles = set(membership.role_assignments.values_list("role_id", flat=True))
    MembershipRoleAssignment.objects.bulk_create(
        [
            MembershipRoleAssignment(
                organization=organization,
                membership=membership,
                role=role,
                scope=role_scopes[str(role.pk)],
                assigned_by=invitation.invited_by,
            )
            for role in roles
            if role.pk not in existing_roles
        ]
    )
    branches = Branch.objects.filter(organization=organization, pk__in=invitation.branch_ids)
    existing_branches = set(membership.branch_access.values_list("branch_id", flat=True))
    MembershipBranchAccess.objects.bulk_create(
        [
            MembershipBranchAccess(
                organization=organization,
                membership=membership,
                branch=branch,
                granted_by=invitation.invited_by,
            )
            for branch in branches
            if branch.pk not in existing_branches
        ]
    )

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save(update_fields=["status", "accepted_at", "accepted_by", "updated_at"])
    if invitation.is_owner and organization.onboarding_status != OnboardingStatus.COMPLETED:
        organization.onboarding_status = OnboardingStatus.COMPLETED
        organization.save(update_fields=["onboarding_status", "updated_at"])

    record_event(
        action="members.invitation_accepted",
        actor=user,
        organization=organization,
        target=membership,
        metadata={"email": user.email, "new_account": created_user},
        request=request,
    )
    return membership, user, created_user
