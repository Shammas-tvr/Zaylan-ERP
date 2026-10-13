from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.tenancy.api.base import TenantScopedViewSet

from .. import services
from ..models import Sale, SaleStatus
from .serializers import SaleSerializer, SaleWriteSerializer


class SaleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = SaleSerializer
    queryset = Sale.objects.select_related("branch").prefetch_related("lines__item")
    required_feature = "pos"
    permission_rules = {
        "list": "sales.view",
        "retrieve": "sales.view",
        "create": "pos.sell",
        "void": "pos.refund",
        "refund": "pos.refund",
    }
    branch_scoped_actions = ("list", "retrieve", "create", "void", "refund")

    def get_queryset(self):
        queryset = super().get_queryset()
        ctx = self.request.tenant
        if ctx.has_permission("sales.view"):
            return queryset
        return queryset.filter(branch_id__in=ctx.branch_ids_with("sales.view"))

    def get_permission_branch_id(self, sale: Sale):
        return sale.branch_id

    @extend_schema(request=SaleWriteSerializer, responses={201: SaleSerializer})
    def create(self, request):
        serializer = SaleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = services.record_sale(request.tenant, serializer.validated_data, request=request)
        sale = self.get_queryset().get(pk=sale.pk)
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    def _reverse(self, request, sale_status):
        sale = services.reverse_sale(
            request.tenant, self.get_object(), status=sale_status, request=request
        )
        return Response(SaleSerializer(self.get_queryset().get(pk=sale.pk)).data)

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        return self._reverse(request, SaleStatus.VOIDED)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        return self._reverse(request, SaleStatus.REFUNDED)
