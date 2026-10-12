from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.tenancy.api.base import TenantScopedViewSet

from .. import services
from ..models import Branch, MembershipBranchAccess
from .serializers import BranchMemberSerializer, BranchSerializer


class BranchViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    TenantScopedViewSet,
):
    serializer_class = BranchSerializer
    queryset = Branch.objects.all()
    permission_rules = {
        "list": "branches.view",
        "retrieve": "branches.view",
        "create": "branches.manage",
        "partial_update": "branches.manage",
        "members": "members.view",
    }
    branch_scoped_actions = ("list", "retrieve", "partial_update", "members")
    search_fields = ("code", "name", "city")
    ordering_fields = ("name", "code", "created_at")
    filterset_fields = ("status",)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in self.branch_scoped_actions:
            code = self.permission_rules.get(self.action, "branches.view")
            return queryset.filter(pk__in=self.request.tenant.branch_ids_with(code))
        return queryset

    def get_permission_branch_id(self, branch: Branch):
        return branch.pk

    @extend_schema(request=BranchSerializer, responses={201: BranchSerializer})
    def create(self, request):
        serializer = BranchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = services.create_branch(request.tenant, serializer.validated_data, request=request)
        return Response(BranchSerializer(branch).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=BranchSerializer, responses=BranchSerializer)
    def partial_update(self, request, pk=None):
        branch = self.get_object()
        serializer = BranchSerializer(branch, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        branch = services.update_branch(
            request.tenant, branch, serializer.validated_data, request=request
        )
        return Response(BranchSerializer(branch).data)

    @extend_schema(responses=BranchMemberSerializer(many=True))
    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        branch = self.get_object()
        access = MembershipBranchAccess.objects.filter(
            organization=request.tenant.organization, branch=branch
        ).select_related("membership__user")
        return Response(BranchMemberSerializer(access, many=True).data)
