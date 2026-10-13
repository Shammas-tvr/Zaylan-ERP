from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.access_control.models import AssignmentScope, MembershipRoleAssignment
from apps.access_control.services import ensure_can_grant, role_permission_codes
from apps.audit_logs.services import record_event
from apps.branches.models import MembershipBranchAccess
from apps.core.exceptions import BusinessRuleViolation, ConflictError
from apps.subscriptions.services import enforce_limit, organization_usage

from ..models import MembershipStatus, OrganizationMembership


@transaction.atomic
def create_staff_member(
    ctx,
    *,
    username: str,
    password: str,
    full_name: str,
    role,
    scope: str,
    branches: list,
    request=None,
) -> OrganizationMembership:
    """Create a brand staff account with username + password only (no email/phone collected)."""
    username = (username or "").strip()
    if len(username) < 3:
        raise ValidationError({"username": ["Username must be at least 3 characters."]})
    if not username.replace("_", "").replace(".", "").isalnum():
        raise ValidationError(
            {"username": ["Use letters, numbers, dots, or underscores only."]}
        )
    validate_password(password)
    usage = organization_usage(ctx.organization)
    enforce_limit(ctx.entitlements, "members", usage["members"] + 1)
    ensure_can_grant(ctx, role_permission_codes([role.pk]))

    User = get_user_model()
    if User.objects.filter(username__iexact=username).exists():
        raise ConflictError("This username is already taken.")

    # Internal email satisfies the unique email column; staff login uses username.
    internal_email = f"{username.lower()}@{ctx.organization.slug}.staff.zaylan.local"
    if User.objects.filter(email__iexact=internal_email).exists():
        raise ConflictError("This username is already taken.")

    try:
        user = User.objects.create_user(
            email=internal_email,
            password=password,
            username=username,
            full_name=(full_name or username).strip()[:150],
        )
    except IntegrityError as exc:
        raise ConflictError("This username is already taken.") from exc

    membership = OrganizationMembership.objects.create(
        organization=ctx.organization,
        user=user,
        status=MembershipStatus.ACTIVE,
        is_owner=False,
    )
    MembershipRoleAssignment.objects.create(
        organization=ctx.organization,
        membership=membership,
        role=role,
        scope=scope,
        assigned_by=ctx.user,
    )
    if scope == AssignmentScope.BRANCHES:
        for branch in branches:
            MembershipBranchAccess.objects.create(
                organization=ctx.organization, membership=membership, branch=branch
            )
    record_event(
        action="members.staff_created",
        actor=ctx.user,
        organization=ctx.organization,
        target=membership,
        metadata={"username": username, "role": role.name},
        request=request,
    )
    return membership


@transaction.atomic
def change_membership_status(ctx, membership, status: str, *, request=None):
    membership = OrganizationMembership.objects.select_for_update().get(
        pk=membership.pk, organization=ctx.organization
    )
    if membership.pk == ctx.membership.pk:
        raise PermissionDenied("You cannot change your own membership status.")
    if membership.is_owner:
        raise BusinessRuleViolation("The organization owner cannot be suspended.")
    if status not in MembershipStatus.values:
        raise BusinessRuleViolation("Unknown membership status.")
    if membership.status == status:
        return membership
    if status == MembershipStatus.ACTIVE:
        from apps.subscriptions.services import enforce_limit

        active = ctx.organization.memberships.filter(status=MembershipStatus.ACTIVE).count()
        enforce_limit(ctx.entitlements, "members", active)
    previous = membership.status
    membership.status = status
    membership.save(update_fields=["status", "updated_at"])
    record_event(
        action="members.status_changed",
        actor=ctx.user,
        organization=ctx.organization,
        target=membership,
        metadata={"email": membership.user.email, "from": previous, "to": status},
        request=request,
    )
    return membership
