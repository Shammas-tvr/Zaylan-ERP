"""Code-owned permission catalog and role templates.

Permission codes follow ``resource.action``. Where a permission applies is decided by the scope of
the role assignment (whole tenant or the member's assigned branches), never by the role name.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDef:
    code: str
    name: str
    module: str
    description: str = ""


@dataclass(frozen=True)
class RoleTemplate:
    key: str
    name: str
    description: str
    permissions: frozenset[str]
    default_scope: str


TENANT_PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef("organization.view", "View organization", "organization"),
    PermissionDef(
        "organization.manage",
        "Manage organization",
        "organization",
        "Edit the organization profile, regional and tax settings, and branding.",
    ),
    PermissionDef("branches.view", "View branches", "branches"),
    PermissionDef("branches.manage", "Manage branches", "branches"),
    PermissionDef("members.view", "View members", "members"),
    PermissionDef(
        "members.manage",
        "Manage members",
        "members",
        "Invite members, suspend members and change their branch access.",
    ),
    PermissionDef("roles.view", "View roles", "roles"),
    PermissionDef("roles.manage", "Manage roles", "roles", "Create roles and assign them."),
    PermissionDef("subscription.view", "View subscription", "subscription"),
    PermissionDef("audit.view", "View audit log", "audit"),
)

PLATFORM_PERMISSIONS: tuple[PermissionDef, ...] = (
    PermissionDef("platform.tenants.view", "View tenants", "platform"),
    PermissionDef(
        "platform.tenants.manage",
        "Manage tenants",
        "platform",
        "Onboard tenants and change their lifecycle status and subscription.",
    ),
    PermissionDef("platform.plans.view", "View plans", "platform"),
    PermissionDef("platform.plans.manage", "Manage plans", "platform"),
    PermissionDef("platform.metrics.view", "View platform metrics", "platform"),
    PermissionDef("platform.audit.view", "View platform audit log", "platform"),
)

TENANT_PERMISSION_CODES = frozenset(p.code for p in TENANT_PERMISSIONS)
PLATFORM_PERMISSION_CODES = frozenset(p.code for p in PLATFORM_PERMISSIONS)

OWNER_ROLE_KEY = "owner"

TENANT_ROLE_TEMPLATES: tuple[RoleTemplate, ...] = (
    RoleTemplate(
        OWNER_ROLE_KEY,
        "Owner / Admin",
        "Full control of the organization. Has no platform administration rights.",
        TENANT_PERMISSION_CODES,
        "TENANT",
    ),
    RoleTemplate(
        "branch_manager",
        "Branch Manager",
        "Runs assigned branches.",
        frozenset({"organization.view", "branches.view", "members.view"}),
        "BRANCHES",
    ),
    RoleTemplate(
        "cashier",
        "Cashier",
        "Operates the POS in assigned branches. Cannot see organization totals.",
        frozenset({"organization.view", "branches.view"}),
        "BRANCHES",
    ),
    RoleTemplate(
        "inventory_manager",
        "Inventory Manager",
        "Manages stock in assigned branches.",
        frozenset({"organization.view", "branches.view"}),
        "BRANCHES",
    ),
    RoleTemplate(
        "accountant",
        "Accountant",
        "Works with financial records within the assigned scope.",
        frozenset({"organization.view", "branches.view", "subscription.view", "audit.view"}),
        "TENANT",
    ),
    RoleTemplate(
        "investor",
        "Investor / Partner",
        "Read-only access to explicitly authorized financial information.",
        frozenset({"organization.view"}),
        "TENANT",
    ),
)

PLATFORM_ROLES: dict[str, tuple[str, frozenset[str]]] = {
    "platform_super_admin": ("Platform Super Admin", PLATFORM_PERMISSION_CODES),
    "platform_support": (
        "Platform Support",
        frozenset({"platform.tenants.view", "platform.plans.view", "platform.metrics.view"}),
    ),
}
