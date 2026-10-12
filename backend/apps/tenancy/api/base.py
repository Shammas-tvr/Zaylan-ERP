from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.access_control.permissions import TenantPermission

from ..context import ORGANIZATION_HEADER, resolve_tenant_context


class TenantContextMixin:
    """Resolves ``request.tenant`` after authentication and before permission checks."""

    permission_classes = [IsAuthenticated, TenantPermission]

    def check_permissions(self, request):
        if not request.user or not request.user.is_authenticated:
            self.permission_denied(request)
        request.tenant = resolve_tenant_context(
            request.user, request.headers.get(ORGANIZATION_HEADER)
        )
        super().check_permissions(request)


class TenantAPIView(TenantContextMixin, APIView):
    pass


class TenantScopedViewSet(TenantContextMixin, viewsets.GenericViewSet):
    """
    Querysets are always filtered to the resolved organization, so object lookups by ID can never
    reach another tenant's rows and respond with 404 instead.
    """

    tenant_field = "organization"
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.tenant_field: self.request.tenant.organization})
