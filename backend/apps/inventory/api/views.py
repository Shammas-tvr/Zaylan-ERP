from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.tenancy.api.base import TenantAPIView, TenantScopedViewSet

from .. import services
from ..models import ProductionOrder, StockBalance, StockTransfer
from .serializers import (
    AdjustmentSerializer,
    BalanceSerializer,
    LocationSerializer,
    ProductionCompleteSerializer,
    ProductionSerializer,
    ProductionWriteSerializer,
    ReceiveSerializer,
    TransferSerializer,
    TransferWriteSerializer,
)


class LocationView(TenantAPIView):
    required_feature = "inventory"
    permission_rules = {"get": "inventory.view"}
    branch_scoped_actions = ("get",)

    def get(self, request):
        if not request.tenant.has_permission_anywhere("inventory.view"):
            self.permission_denied(request)
        rows = services.visible_locations(request.tenant).order_by("name")
        return Response(LocationSerializer(rows, many=True).data)


class BalanceView(TenantAPIView):
    required_feature = "inventory"
    permission_rules = {"get": "inventory.view"}
    branch_scoped_actions = ("get",)

    def get(self, request):
        if not request.tenant.has_permission_anywhere("inventory.view"):
            self.permission_denied(request)
        locations = services.visible_locations(request.tenant)
        rows = (
            StockBalance.objects.filter(
                organization=request.tenant.organization, location__in=locations
            )
            .select_related("item", "location")
            .order_by("location__name", "item__name")
        )
        return Response(BalanceSerializer(rows, many=True).data)


class AdjustmentView(TenantAPIView):
    required_feature = "inventory"
    permission_rules = {"post": "inventory.adjust"}

    @extend_schema(request=AdjustmentSerializer)
    def post(self, request):
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = services.adjust_stock(
            request.tenant, serializer.validated_data, request=request
        )
        return Response({"id": movement.pk, "quantity": movement.quantity}, status=status.HTTP_201_CREATED)


class ProductionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet
):
    serializer_class = ProductionSerializer
    queryset = ProductionOrder.objects.select_related("recipe__output_item")
    required_feature = "production"
    permission_rules = {
        "list": "production.manage",
        "retrieve": "production.manage",
        "create": "production.manage",
        "complete": "production.manage",
    }

    @extend_schema(request=ProductionWriteSerializer, responses={201: ProductionSerializer})
    def create(self, request):
        serializer = ProductionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.create_production(
            request.tenant, serializer.validated_data, request=request
        )
        return Response(ProductionSerializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ProductionCompleteSerializer, responses=ProductionSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        order = self.get_object()
        serializer = ProductionCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.complete_production(
            request.tenant, order, serializer.validated_data, request=request
        )
        return Response(ProductionSerializer(order).data)


class TransferViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = TransferSerializer
    queryset = StockTransfer.objects.select_related("destination_location").prefetch_related(
        "lines__item"
    )
    required_feature = "inventory"
    permission_rules = {
        "list": "inventory.view",
        "retrieve": "inventory.view",
        "create": "inventory.dispatch",
        "approve": "inventory.dispatch",
        "dispatch": "inventory.dispatch",
        "receive": "inventory.receive",
        "close": "inventory.adjust",
    }
    branch_scoped_actions = ("list", "retrieve", "receive")

    def get_queryset(self):
        queryset = super().get_queryset()
        ctx = self.request.tenant
        if ctx.has_permission("inventory.dispatch") or ctx.has_permission("inventory.view"):
            return queryset
        branch_ids = ctx.branch_ids_with("inventory.view") | ctx.branch_ids_with("inventory.receive")
        return queryset.filter(destination_location__branch_id__in=branch_ids)

    def get_permission_branch_id(self, transfer: StockTransfer):
        return transfer.destination_location.branch_id

    @extend_schema(request=TransferWriteSerializer, responses={201: TransferSerializer})
    def create(self, request):
        serializer = TransferWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = services.create_transfer(
            request.tenant, serializer.validated_data, request=request
        )
        transfer = self.get_queryset().get(pk=transfer.pk)
        return Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        transfer = services.approve_transfer(request.tenant, self.get_object(), request=request)
        return Response(TransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)

    @action(detail=True, methods=["post"])
    def dispatch(self, request, pk=None):
        transfer = services.dispatch_transfer(request.tenant, self.get_object(), request=request)
        return Response(TransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)

    @extend_schema(request=ReceiveSerializer, responses=TransferSerializer)
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        serializer = ReceiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = services.receive_transfer(
            request.tenant, self.get_object(), serializer.validated_data, request=request
        )
        return Response(TransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        transfer = services.close_transfer(request.tenant, self.get_object(), request=request)
        return Response(TransferSerializer(self.get_queryset().get(pk=transfer.pk)).data)

