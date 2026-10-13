"""Server-side resolution of the tenant a request operates in.

The ``X-Organization-ID`` header only *selects* an organization. Access is granted solely by an
active membership, and every permission is computed here from the database on each request.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from apps.core.exceptions import OrganizationRequired, OrganizationUnavailable, SubscriptionInactive

from .models import MembershipStatus, Organization, OrganizationMembership, OrganizationStatus

# These resources have no branch identity, so holding the permission on a branch-scoped
# role still authorizes the organization-level endpoint.
NON_BRANCHABLE_PERMISSIONS = frozenset(
    {
        "organization.view",
        "organization.manage",
        "subscription.view",
        "roles.view",
        "roles.manage",
        "audit.view",
        "expenses.approve",
        "expenses.pay",
        "expenses.configure",
        "catalog.view",
        "catalog.manage",
        "production.manage",
        "inventory.dispatch",
        "inventory.adjust",
    }
)

ORGANIZATION_HEADER = "X-Organization-ID"


@dataclass(frozen=True)
class TenantContext:
    user: object
    organization: Organization
    membership: OrganizationMembership
    # Permissions that apply across the whole organization.
    tenant_permissions: frozenset[str]
    # Effective permissions per accessible branch (already includes tenant-wide permissions).
    branch_permissions: Mapping[uuid.UUID, frozenset[str]]
    entitlements: Mapping[str, object] = field(default_factory=dict)

    @property
    def accessible_branch_ids(self) -> frozenset[uuid.UUID]:
        return frozenset(self.branch_permissions)

    def has_permission(self, code: str, branch_id: uuid.UUID | None = None) -> bool:
        if branch_id is None:
            return code in self.tenant_permissions
        return code in self.branch_permissions.get(branch_id, frozenset())

    def has_permission_anywhere(self, code: str) -> bool:
        return code in self.tenant_permissions or any(
            code in perms for perms in self.branch_permissions.values()
        )

    def branch_ids_with(self, code: str) -> frozenset[uuid.UUID]:
        return frozenset(bid for bid, perms in self.branch_permissions.items() if code in perms)

    def feature_enabled(self, code: str) -> bool:
        entitlement = self.entitlements.get(code)
        return bool(entitlement and entitlement.enabled)

    def all_permission_codes(self) -> frozenset[str]:
        codes = set(self.tenant_permissions)
        for perms in self.branch_permissions.values():
            codes |= perms
        return frozenset(codes)


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def resolve_tenant_context(user, organization_id: str | None) -> TenantContext:
    from apps.access_control.models import AssignmentScope, MembershipRoleAssignment, RolePermission
    from apps.branches.models import Branch, BranchStatus, MembershipBranchAccess
    from apps.subscriptions.services import get_entitlements, subscription_allows_access

    if not organization_id:
        raise OrganizationRequired()
    org_uuid = _parse_uuid(organization_id)
    if org_uuid is None or not getattr(user, "is_authenticated", False):
        raise OrganizationUnavailable()

    membership = (
        OrganizationMembership.objects.select_related("organization", "organization__subscription")
        .filter(user=user, organization_id=org_uuid, status=MembershipStatus.ACTIVE)
        .first()
    )
    if membership is None or membership.organization.status != OrganizationStatus.ACTIVE:
        raise OrganizationUnavailable()
    organization = membership.organization

    subscription = getattr(organization, "subscription", None)
    if not subscription_allows_access(subscription):
        raise SubscriptionInactive()

    assignments = list(
        MembershipRoleAssignment.objects.filter(
            membership=membership, organization=organization
        ).values_list("role_id", "scope")
    )
    permissions_by_role: dict[uuid.UUID, set[str]] = {}
    for role_id, code in RolePermission.objects.filter(
        role_id__in=[role_id for role_id, _ in assignments],
        role__organization=organization,
    ).values_list("role_id", "permission__code"):
        permissions_by_role.setdefault(role_id, set()).add(code)

    tenant_permissions: set[str] = set()
    branch_scoped_permissions: set[str] = set()
    for role_id, scope in assignments:
        codes = permissions_by_role.get(role_id, set())
        if scope == AssignmentScope.TENANT:
            tenant_permissions |= codes
        else:
            tenant_permissions |= codes & NON_BRANCHABLE_PERMISSIONS
            branch_scoped_permissions |= codes - NON_BRANCHABLE_PERMISSIONS

    explicit_branch_ids = set(
        MembershipBranchAccess.objects.filter(
            membership=membership,
            organization=organization,
            branch__status=BranchStatus.ACTIVE,
        ).values_list("branch_id", flat=True)
    )
    if tenant_permissions:
        # Organization-wide roles reach every branch, including inactive ones for administration.
        all_branch_ids = set(
            Branch.objects.filter(organization=organization).values_list("id", flat=True)
        )
    else:
        all_branch_ids = set()

    frozen_tenant = frozenset(tenant_permissions)
    branch_permissions: dict[uuid.UUID, frozenset[str]] = {
        branch_id: frozen_tenant for branch_id in all_branch_ids
    }
    for branch_id in explicit_branch_ids:
        branch_permissions[branch_id] = frozen_tenant | frozenset(branch_scoped_permissions)

    return TenantContext(
        user=user,
        organization=organization,
        membership=membership,
        tenant_permissions=frozen_tenant,
        branch_permissions=branch_permissions,
        entitlements=get_entitlements(subscription),
    )
