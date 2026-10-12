import uuid
from dataclasses import dataclass

from rest_framework.exceptions import NotFound, PermissionDenied

from apps.branches.models import Branch, MembershipBranchAccess
from apps.tenancy.models import Organization, OrganizationMembership

from .effective import EffectivePermissions, resolve_permissions

ORGANIZATION_HEADER = "X-Organization-ID"


@dataclass(frozen=True)
class TenantContext:
    """Authorized tenant scope for one request, derived entirely on the server."""

    organization: Organization
    membership: OrganizationMembership
    permissions: EffectivePermissions
    branch_ids: frozenset[uuid.UUID]

    @property
    def user(self):
        return self.membership.user

    def can_access_branch(self, branch_id) -> bool:
        return uuid.UUID(str(branch_id)) in self.branch_ids


def resolve_tenant_context(user, organization_id: uuid.UUID) -> TenantContext:
    membership = (
        OrganizationMembership.objects.select_related("organization", "user")
        .filter(
            user=user,
            organization_id=organization_id,
            status=OrganizationMembership.Status.ACTIVE,
        )
        .first()
    )
    # Non-members get the same response as a nonexistent organization to avoid leaking existence.
    if membership is None:
        raise NotFound("Organization not found.")
    if not membership.organization.is_accessible:
        raise PermissionDenied("This organization is not active.", code="organization_inactive")

    permissions = resolve_permissions(membership)
    active_branches = Branch.objects.filter(
        organization_id=organization_id, status=Branch.Status.ACTIVE
    )
    if permissions.tenant_wide:
        branch_ids = frozenset(active_branches.values_list("id", flat=True))
    else:
        branch_ids = frozenset(
            MembershipBranchAccess.objects.filter(
                membership=membership, branch__in=active_branches
            ).values_list("branch_id", flat=True)
        )
    return TenantContext(
        organization=membership.organization,
        membership=membership,
        permissions=permissions,
        branch_ids=branch_ids,
    )
