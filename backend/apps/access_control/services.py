from collections.abc import Iterable

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError

from .catalog import (
    OWNER_ROLE_KEY,
    PLATFORM_PERMISSIONS,
    PLATFORM_ROLES,
    TENANT_PERMISSION_CODES,
    TENANT_PERMISSIONS,
    TENANT_ROLE_TEMPLATES,
)
from .models import (
    AssignmentScope,
    MembershipRoleAssignment,
    Permission,
    PermissionLevel,
    PlatformRoleAssignment,
    Role,
    RolePermission,
)


def sync_permission_catalog() -> None:
    for level, definitions in (
        (PermissionLevel.TENANT, TENANT_PERMISSIONS),
        (PermissionLevel.PLATFORM, PLATFORM_PERMISSIONS),
    ):
        for definition in definitions:
            Permission.objects.update_or_create(
                code=definition.code,
                defaults={
                    "name": definition.name,
                    "module": definition.module,
                    "description": definition.description,
                    "level": level,
                },
            )


def sync_permission_catalog_on_migrate(**kwargs) -> None:
    sync_permission_catalog()


def _set_role_permissions(role: Role, codes: Iterable[str]) -> None:
    codes = set(codes)
    unknown = codes - TENANT_PERMISSION_CODES
    if unknown:
        raise ValidationError({"permission_codes": [f"Unknown permissions: {sorted(unknown)}"]})
    permissions = Permission.objects.filter(code__in=codes, level=PermissionLevel.TENANT)
    RolePermission.objects.filter(role=role).exclude(permission__in=permissions).delete()
    existing = set(RolePermission.objects.filter(role=role).values_list("permission_id", flat=True))
    RolePermission.objects.bulk_create(
        [RolePermission(role=role, permission=p) for p in permissions if p.pk not in existing]
    )


@transaction.atomic
def sync_system_roles(organization) -> dict[str, Role]:
    """Create or refresh the immutable role templates for one organization."""
    sync_permission_catalog()
    roles = {}
    for template in TENANT_ROLE_TEMPLATES:
        role, _ = Role.objects.update_or_create(
            organization=organization,
            key=template.key,
            defaults={
                "name": template.name,
                "description": template.description,
                "is_system": True,
            },
        )
        _set_role_permissions(role, template.permissions)
        roles[template.key] = role
    return roles


def owner_role(organization) -> Role:
    return Role.objects.get(organization=organization, key=OWNER_ROLE_KEY)


def role_permission_codes(role_ids: Iterable) -> set[str]:
    return set(
        RolePermission.objects.filter(role_id__in=list(role_ids)).values_list(
            "permission__code", flat=True
        )
    )


def ensure_can_grant(ctx, codes: Iterable[str]) -> None:
    """Prevent privilege escalation: a member can only grant permissions they hold tenant-wide."""
    missing = set(codes) - ctx.tenant_permissions
    if missing:
        raise PermissionDenied("You cannot grant permissions that you do not hold yourself.")


@transaction.atomic
def create_role(ctx, *, name: str, description: str, permission_codes: list[str], request=None):
    ensure_can_grant(ctx, permission_codes)
    if Role.objects.filter(organization=ctx.organization, name__iexact=name).exists():
        raise ConflictError("A role with this name already exists.")
    role = Role.objects.create(organization=ctx.organization, name=name, description=description)
    _set_role_permissions(role, permission_codes)
    record_event(
        action="roles.created",
        actor=ctx.user,
        organization=ctx.organization,
        target=role,
        metadata={"name": name, "permissions": sorted(permission_codes)},
        request=request,
    )
    return role


@transaction.atomic
def update_role(ctx, role: Role, *, request=None, **changes) -> Role:
    role = Role.objects.select_for_update().get(pk=role.pk, organization=ctx.organization)
    if role.is_system:
        raise BusinessRuleViolation("System roles cannot be changed. Create a custom role instead.")
    if "name" in changes and changes["name"].lower() != role.name.lower():
        if Role.objects.filter(
            organization=ctx.organization, name__iexact=changes["name"]
        ).exists():
            raise ConflictError("A role with this name already exists.")
    for field in ("name", "description"):
        if field in changes:
            setattr(role, field, changes[field])
    role.save()
    if "permission_codes" in changes:
        ensure_can_grant(ctx, changes["permission_codes"])
        _set_role_permissions(role, changes["permission_codes"])
    record_event(
        action="roles.updated",
        actor=ctx.user,
        organization=ctx.organization,
        target=role,
        metadata={k: sorted(v) if isinstance(v, list) else v for k, v in changes.items()},
        request=request,
    )
    return role


@transaction.atomic
def delete_role(ctx, role: Role, *, request=None) -> None:
    role = Role.objects.select_for_update().get(pk=role.pk, organization=ctx.organization)
    if role.is_system:
        raise BusinessRuleViolation("System roles cannot be deleted.")
    if role.assignments.exists():
        raise ConflictError("Remove this role from all members before deleting it.")
    record_event(
        action="roles.deleted",
        actor=ctx.user,
        organization=ctx.organization,
        target=role,
        metadata={"name": role.name},
        request=request,
    )
    role.delete()


@transaction.atomic
def set_member_roles(ctx, membership, assignments: list[dict], *, request=None) -> None:
    """Replace a member's role assignments (``[{"role": Role, "scope": str}]``)."""
    from apps.tenancy.models import OrganizationMembership

    membership = OrganizationMembership.objects.select_for_update().get(
        pk=membership.pk, organization=ctx.organization
    )
    if membership.pk == ctx.membership.pk and not membership.is_owner:
        raise PermissionDenied("You cannot change your own roles.")

    roles = [item["role"] for item in assignments]
    if any(role.organization_id != ctx.organization.pk for role in roles):
        raise ValidationError({"assignments": ["Unknown role."]})
    if len({role.pk for role in roles}) != len(roles):
        raise ValidationError({"assignments": ["A role can only be assigned once."]})

    current = MembershipRoleAssignment.objects.filter(membership=membership)
    current_role_ids = set(current.values_list("role_id", flat=True))
    new_role_ids = {role.pk for role in roles}
    # Both added and removed permissions must be within the actor's own authority.
    ensure_can_grant(ctx, role_permission_codes(current_role_ids ^ new_role_ids))

    if membership.is_owner:
        owner = owner_role(ctx.organization)
        if not any(
            item["role"].pk == owner.pk and item["scope"] == AssignmentScope.TENANT
            for item in assignments
        ):
            raise BusinessRuleViolation("The owner must keep the Owner role for the organization.")

    current.delete()
    MembershipRoleAssignment.objects.bulk_create(
        [
            MembershipRoleAssignment(
                organization=ctx.organization,
                membership=membership,
                role=item["role"],
                scope=item["scope"],
                assigned_by=ctx.user,
            )
            for item in assignments
        ]
    )
    record_event(
        action="members.roles_changed",
        actor=ctx.user,
        organization=ctx.organization,
        target=membership,
        metadata={
            "assignments": [
                {"role": item["role"].name, "scope": item["scope"]} for item in assignments
            ]
        },
        request=request,
    )


def platform_permissions_for(user) -> frozenset[str]:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return frozenset()
    keys = PlatformRoleAssignment.objects.filter(user=user, revoked_at__isnull=True).values_list(
        "role_key", flat=True
    )
    codes: set[str] = set()
    for key in keys:
        if key in PLATFORM_ROLES:
            codes |= PLATFORM_ROLES[key][1]
    return frozenset(codes)


@transaction.atomic
def grant_platform_role(*, user, role_key: str, granted_by=None) -> PlatformRoleAssignment:
    if role_key not in PLATFORM_ROLES:
        raise ValidationError({"role_key": ["Unknown platform role."]})
    assignment, created = PlatformRoleAssignment.objects.get_or_create(
        user=user, role_key=role_key, revoked_at__isnull=True, defaults={"granted_by": granted_by}
    )
    if created:
        record_event(
            action="platform.role_granted",
            actor=granted_by,
            target=user,
            metadata={"role": role_key},
        )
    return assignment
