"""DRF building blocks that every tenant-scoped and platform API must use."""

import uuid

from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated

from .catalog import PLATFORM_PERMISSIONS
from .context import ORGANIZATION_HEADER, TenantContext, resolve_tenant_context
from .models import PlatformRoleAssignment

ANY_MEMBER = "__any_member__"


def get_tenant_context(request) -> TenantContext:
    cached = getattr(request, "_tenant_context", None)
    if cached is not None:
        return cached
    raw = request.headers.get(ORGANIZATION_HEADER)
    if not raw:
        raise ValidationError({"organization": [f"The {ORGANIZATION_HEADER} header is required."]})
    try:
        organization_id = uuid.UUID(raw)
    except ValueError as exc:
        raise NotFound("Organization not found.") from exc
    context = resolve_tenant_context(request.user, organization_id)
    request._tenant_context = context
    return context


class HasTenantPermission(BasePermission):
    """Resolves the tenant context and requires the view's permission at some scope.

    Views must narrow branch scope themselves (querysets or `require`). Unmapped actions are denied.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        context = get_tenant_context(request)
        code = view.get_required_permission()
        if code is None:
            return False
        if code == ANY_MEMBER:
            return True
        return context.permissions.has_any(code)


class TenantAPIMixin:
    permission_classes = [IsAuthenticated, HasTenantPermission]
    permission_map: dict[str, str] = {}

    def get_required_permission(self) -> str | None:
        key = getattr(self, "action", None) or self.request.method.lower()
        return self.permission_map.get(key, self.permission_map.get("*"))

    @property
    def tenant(self) -> TenantContext:
        return get_tenant_context(self.request)

    def require(self, code: str, branch_id=None) -> None:
        if not self.tenant.permissions.has(code, branch_id):
            raise PermissionDenied()


class TenantScopedViewSet(TenantAPIMixin, viewsets.GenericViewSet):
    """Queries are always filtered to the requester's organization, so foreign IDs return 404."""

    def get_base_queryset(self):
        raise NotImplementedError

    def get_queryset(self):
        return self.get_base_queryset().filter(organization_id=self.tenant.organization.id)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["tenant"] = self.tenant
        return context


def platform_permissions(user) -> frozenset[str]:
    if not (user and user.is_authenticated and user.is_active):
        return frozenset()
    roles = PlatformRoleAssignment.objects.filter(user=user).values_list("role", flat=True)
    codes: set[str] = set()
    for role in roles:
        codes |= PLATFORM_PERMISSIONS.get(role, frozenset())
    return frozenset(codes)


class HasPlatformPermission(BasePermission):
    def has_permission(self, request, view):
        code = view.get_required_permission()
        if code is None:
            return False
        if not hasattr(request, "_platform_permissions"):
            request._platform_permissions = platform_permissions(request.user)
        return code in request._platform_permissions


class PlatformAPIMixin:
    permission_classes = [IsAuthenticated, HasPlatformPermission]
    permission_map: dict[str, str] = {}

    def get_required_permission(self) -> str | None:
        key = getattr(self, "action", None) or self.request.method.lower()
        return self.permission_map.get(key, self.permission_map.get("*"))
