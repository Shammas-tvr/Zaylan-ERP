from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import ConflictError
from apps.subscriptions.services import enforce_limit, organization_usage

from .models import Branch, MembershipBranchAccess

BRANCH_FIELDS = (
    "code",
    "name",
    "status",
    "timezone",
    "phone",
    "email",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
)


def _save_branch(branch: Branch) -> None:
    branch.code = branch.code.strip().upper()
    branch.full_clean(validate_constraints=False)
    try:
        with transaction.atomic():
            branch.save()
    except IntegrityError as exc:
        raise ConflictError("A branch with this code already exists.") from exc


@transaction.atomic
def create_branch(ctx, data: dict, *, request=None) -> Branch:
    # Lock the organization row so concurrent creations cannot both pass the plan limit.
    type(ctx.organization).objects.select_for_update().get(pk=ctx.organization.pk)
    enforce_limit(
        ctx.entitlements, "branches", Branch.objects.filter(organization=ctx.organization).count()
    )
    branch = Branch(
        organization=ctx.organization, **{f: data[f] for f in BRANCH_FIELDS if f in data}
    )
    _save_branch(branch)
    from apps.inventory.services import ensure_branch_location

    ensure_branch_location(branch)
    username = (data.get("login_username") or "").strip()
    password = data.get("login_password") or ""
    if username or password:
        _attach_branch_login(ctx, branch, username, password)
    record_event(
        action="branches.created",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=branch,
        metadata={"code": branch.code, "name": branch.name},
        request=request,
    )
    return branch


@transaction.atomic
def update_branch(ctx, branch: Branch, data: dict, *, request=None) -> Branch:
    branch = Branch.objects.select_for_update().get(pk=branch.pk, organization=ctx.organization)
    changed = {}
    for field in BRANCH_FIELDS:
        if field in data and getattr(branch, field) != data[field]:
            changed[field] = [getattr(branch, field), data[field]]
            setattr(branch, field, data[field])
    if changed:
        _save_branch(branch)
        from apps.inventory.services import ensure_branch_location

        ensure_branch_location(branch)
        record_event(
            action="branches.updated",
            actor=ctx.user,
            organization=ctx.organization,
            branch=branch,
            target=branch,
            metadata=changed,
            request=request,
        )
    username = (data.get("login_username") or "").strip()
    password = data.get("login_password") or ""
    if branch.login_user_id and password:
        validate_password(password, user=branch.login_user)
        branch.login_user.set_password(password)
        branch.login_user.save(update_fields=["password"])
        record_event(
            action="branches.login_reset",
            actor=ctx.user,
            organization=ctx.organization,
            branch=branch,
            target=branch,
            metadata={"username": branch.login_user.username},
            request=request,
        )
    elif username and password and branch.login_user_id is None:
        _attach_branch_login(ctx, branch, username, password)
    return branch


def _attach_branch_login(ctx, branch: Branch, username: str, password: str) -> None:
    from apps.access_control.models import AssignmentScope, MembershipRoleAssignment
    from apps.access_control.services import sync_system_roles
    from apps.tenancy.models import MembershipStatus, OrganizationMembership

    if len(username) < 3 or not username.replace("_", "").replace(".", "").isalnum():
        raise ValidationError(
            {"login_username": ["Use at least 3 letters, numbers, dots, or underscores."]}
        )
    User = get_user_model()
    if User.objects.filter(username__iexact=username).exists():
        raise ConflictError("This username is already taken.")
    validate_password(password)
    usage = organization_usage(ctx.organization)
    enforce_limit(ctx.entitlements, "members", usage["members"] + 1)
    roles = sync_system_roles(ctx.organization)
    internal_email = f"{username.lower()}@{ctx.organization.slug}.branch.zaylan.local"
    try:
        user = User.objects.create_user(
            email=internal_email,
            password=password,
            username=username,
            full_name=branch.name[:150],
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
        role=roles["branch_login"],
        scope=AssignmentScope.BRANCHES,
        assigned_by=ctx.user,
    )
    MembershipBranchAccess.objects.create(
        organization=ctx.organization,
        membership=membership,
        branch=branch,
        granted_by=ctx.user,
    )
    branch.login_user = user
    branch.save(update_fields=["login_user", "updated_at"])


def resolve_branches(ctx, branch_ids) -> list[Branch]:
    """Look up IDs inside the tenant; unknown and foreign IDs are reported identically."""
    unique_ids = {str(b) for b in branch_ids}
    branches = list(Branch.objects.filter(organization=ctx.organization, pk__in=unique_ids))
    if len(branches) != len(unique_ids):
        raise ValidationError({"branch_ids": ["One or more branches do not exist."]})
    return branches


@transaction.atomic
def set_member_branch_access(ctx, membership, branches: list[Branch], *, request=None) -> None:
    from apps.tenancy.models import OrganizationMembership

    membership = OrganizationMembership.objects.select_for_update().get(
        pk=membership.pk, organization=ctx.organization
    )
    if membership.pk == ctx.membership.pk and not membership.is_owner:
        raise PermissionDenied("You cannot change your own branch access.")
    if any(branch.organization_id != ctx.organization.pk for branch in branches):
        raise ValidationError({"branch_ids": ["One or more branches do not exist."]})

    new_ids = {branch.pk for branch in branches}
    current = MembershipBranchAccess.objects.filter(membership=membership)
    current_ids = set(current.values_list("branch_id", flat=True))
    current.exclude(branch_id__in=new_ids).delete()
    MembershipBranchAccess.objects.bulk_create(
        [
            MembershipBranchAccess(
                organization=ctx.organization,
                membership=membership,
                branch=branch,
                granted_by=ctx.user,
            )
            for branch in branches
            if branch.pk not in current_ids
        ]
    )
    record_event(
        action="members.branch_access_changed",
        actor=ctx.user,
        organization=ctx.organization,
        target=membership,
        metadata={
            "added": sorted(b.code for b in branches if b.pk not in current_ids),
            "removed_count": len(current_ids - new_ids),
        },
        request=request,
    )
