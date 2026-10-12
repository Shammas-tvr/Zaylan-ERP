from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel, UUIDModel

from .catalog import PLATFORM_ROLES


class PermissionLevel(models.TextChoices):
    TENANT = "TENANT", "Tenant"
    PLATFORM = "PLATFORM", "Platform"


class Permission(UUIDModel):
    """Synchronized from ``catalog.py``; never edited through the API."""

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    module = models.CharField(max_length=50)
    description = models.CharField(max_length=500, blank=True)
    level = models.CharField(max_length=16, choices=PermissionLevel.choices)

    class Meta:
        ordering = ["module", "code"]

    def __str__(self) -> str:
        return self.code


class Role(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="roles"
    )
    # Template key for system roles; blank for tenant-defined custom roles.
    key = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    is_system = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, through="RolePermission", related_name="roles")

    class Meta:
        ordering = ["-is_system", "name"]
        constraints = [
            models.UniqueConstraint(
                "organization", Lower("name"), name="access_control_role_org_name_unique"
            ),
            models.UniqueConstraint(
                fields=["organization", "key"],
                condition=~Q(key=""),
                name="access_control_role_org_key_unique",
            ),
            models.UniqueConstraint(
                fields=["organization", "id"], name="access_control_role_org_id_unique"
            ),
            models.CheckConstraint(
                condition=Q(is_system=False) | ~Q(key=""),
                name="access_control_role_system_has_key",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class RolePermission(UUIDModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="access_control_role_permission_unique"
            ),
        ]


class AssignmentScope(models.TextChoices):
    TENANT = "TENANT", "Entire organization"
    BRANCHES = "BRANCHES", "Assigned branches"


class MembershipRoleAssignment(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="+"
    )
    membership = models.ForeignKey(
        "tenancy.OrganizationMembership", on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    scope = models.CharField(max_length=16, choices=AssignmentScope.choices)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role"], name="access_control_assignment_unique"
            ),
        ]
        indexes = [models.Index(fields=["organization", "membership"])]


class PlatformRoleAssignment(TimeStampedModel):
    """Platform roles are independent of tenant memberships and grant no tenant data access."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="platform_roles"
    )
    role_key = models.CharField(
        max_length=50, choices=[(k, v[0]) for k, v in PLATFORM_ROLES.items()]
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role_key"],
                condition=Q(revoked_at__isnull=True),
                name="access_control_platform_role_active_unique",
            ),
        ]
