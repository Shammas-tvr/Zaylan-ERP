from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.response import Response

from apps.tenancy.api.base import TenantAPIView, TenantScopedViewSet

from .. import services
from ..models import Permission, PermissionLevel, Role, RolePermission
from .serializers import PermissionSerializer, RoleSerializer, RoleWriteSerializer


class PermissionCatalogView(TenantAPIView):
    permission_rules = {"get": "roles.view"}

    @extend_schema(responses=PermissionSerializer(many=True))
    def get(self, request):
        permissions = Permission.objects.filter(level=PermissionLevel.TENANT)
        return Response(PermissionSerializer(permissions, many=True).data)


class RoleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    serializer_class = RoleSerializer
    queryset = Role.objects.prefetch_related(
        Prefetch("role_permissions", queryset=RolePermission.objects.select_related("permission"))
    )
    pagination_class = None
    permission_rules = {
        "list": "roles.view",
        "retrieve": "roles.view",
        "create": "roles.manage",
        "partial_update": "roles.manage",
        "destroy": "roles.manage",
    }
    feature_rules = {
        "create": "custom_roles",
        "partial_update": "custom_roles",
        "destroy": "custom_roles",
    }

    @extend_schema(request=RoleWriteSerializer, responses={201: RoleSerializer})
    def create(self, request):
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.create_role(request.tenant, **serializer.validated_data, request=request)
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=RoleWriteSerializer, responses=RoleSerializer)
    def partial_update(self, request, pk=None):
        serializer = RoleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        role = services.update_role(
            request.tenant, self.get_object(), **serializer.validated_data, request=request
        )
        return Response(RoleSerializer(self.get_queryset().get(pk=role.pk)).data)

    def destroy(self, request, pk=None):
        services.delete_role(request.tenant, self.get_object(), request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
