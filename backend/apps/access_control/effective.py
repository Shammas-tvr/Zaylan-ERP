import uuid
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field

from django.db.models import Q

from .models import MembershipRoleAssignment


def _as_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


@dataclass(frozen=True)
class EffectivePermissions:
    """Permissions a member holds, either tenant-wide or for specific branches."""

    tenant_wide: frozenset[str] = frozenset()
    by_branch: Mapping[str, frozenset[uuid.UUID]] = field(default_factory=dict)

    def has(self, code: str, branch_id=None) -> bool:
        """With no branch, only a tenant-wide grant qualifies."""
        if code in self.tenant_wide:
            return True
        if branch_id is None:
            return False
        return _as_uuid(branch_id) in self.by_branch.get(code, frozenset())

    def has_any(self, code: str) -> bool:
        return code in self.tenant_wide or bool(self.by_branch.get(code))

    def branch_ids(self, code: str) -> frozenset[uuid.UUID] | None:
        """Branches where `code` is held. None means every branch (tenant-wide grant)."""
        if code in self.tenant_wide:
            return None
        return self.by_branch.get(code, frozenset())

    def as_dict(self) -> dict:
        result: dict = {code: {"scope": "tenant"} for code in sorted(self.tenant_wide)}
        for code, branches in sorted(self.by_branch.items()):
            if code not in self.tenant_wide:
                result[code] = {"scope": "branches", "branch_ids": sorted(str(b) for b in branches)}
        return result


def resolve_permissions(membership) -> EffectivePermissions:
    """Branch-scoped grants count only for active branches the member has access to."""
    rows = (
        MembershipRoleAssignment.objects.filter(membership=membership)
        .filter(
            Q(branch__isnull=True)
            | Q(branch__status="active", branch__member_access__membership=membership)
        )
        .exclude(role__permissions__code__isnull=True)
        .values_list("branch_id", "role__permissions__code")
    )
    tenant_wide: set[str] = set()
    by_branch: dict[str, set[uuid.UUID]] = defaultdict(set)
    for branch_id, code in rows:
        if branch_id is None:
            tenant_wide.add(code)
        else:
            by_branch[code].add(branch_id)
    return EffectivePermissions(
        tenant_wide=frozenset(tenant_wide),
        by_branch={code: frozenset(ids) for code, ids in by_branch.items()},
    )
