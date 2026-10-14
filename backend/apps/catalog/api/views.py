from django.db.models import DecimalField, OuterRef, Prefetch, Subquery
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.inventory.models import StockBalance
from apps.core.storage import create_image_upload
from apps.tenancy.api.base import TenantAPIView, TenantScopedViewSet

from .. import services
from ..models import Item, ItemLocationPolicy, Product, Recipe, Supplier
from .serializers import (
    ItemSerializer,
    ItemWriteSerializer,
    ProductSerializer,
    ProductWriteSerializer,
    RecipeSerializer,
    RecipeWriteSerializer,
    SupplierSerializer,
)


class SupplierViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, TenantScopedViewSet):
    serializer_class = SupplierSerializer
    queryset = Supplier.objects.filter(is_active=True)
    required_feature = "products"
    permission_rules = {"list": "catalog.view", "create": "catalog.manage"}
    search_fields = ("name",)
    ordering_fields = ("name",)

    @extend_schema(request=SupplierSerializer, responses={201: SupplierSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = services.create_supplier(request.tenant, serializer.validated_data["name"])
        return Response(SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED)


class ImageUploadView(TenantAPIView):
    required_feature = "products"
    permission_rules = {"post": "catalog.manage"}

    def post(self, request):
        purpose = request.data.get("purpose") or ""
        content_type = request.data.get("content_type") or ""
        filename = request.data.get("filename") or ""
        return Response(
            create_image_upload(
                organization_id=request.tenant.organization.pk,
                purpose=purpose,
                content_type=content_type,
                filename=filename,
            )
        )


class ItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = ItemSerializer
    queryset = Item.objects.all()
    required_feature = "products"
    permission_rules = {
        "list": "catalog.view",
        "retrieve": "catalog.view",
        "create": "catalog.manage",
        "partial_update": "catalog.manage",
    }
    search_fields = ("sku", "name")
    filterset_fields = ("kind", "is_active")
    ordering_fields = ("name", "sku")

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("default_supplier", "storage_location")
            .prefetch_related("suppliers", "location_policies__location")
        )
        location_id = self.request.query_params.get("location")
        if not location_id:
            return queryset
        if not services._visible_locations(self.request.tenant).filter(pk=location_id).exists():
            raise ValidationError({"location": ["You cannot view stock at that location."]})
        quantity = StockBalance.objects.filter(item=OuterRef("pk"), location_id=location_id).values(
            "quantity"
        )[:1]
        minimum = ItemLocationPolicy.objects.filter(item=OuterRef("pk"), location_id=location_id).values(
            "minimum_quantity"
        )[:1]
        decimal = DecimalField(max_digits=14, decimal_places=3)
        return queryset.annotate(
            branch_quantity_base=Subquery(quantity, output_field=decimal),
            branch_minimum=Subquery(minimum, output_field=decimal),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["stock_location"] = self.request.query_params.get("location") or None
        return context

    @extend_schema(request=ItemWriteSerializer, responses={201: ItemSerializer})
    def create(self, request):
        serializer = ItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = services.create_item(request.tenant, serializer.validated_data, request=request)
        return Response(ItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ItemWriteSerializer, responses=ItemSerializer)
    def partial_update(self, request, pk=None):
        item = self.get_object()
        serializer = ItemWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = services.update_item(request.tenant, item, serializer.validated_data, request=request)
        return Response(ItemSerializer(item).data)


class ProductViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.select_related("inventory_item").prefetch_related(
        "branches",
        Prefetch(
            "recipes",
            queryset=Recipe.objects.filter(is_active=True).prefetch_related("lines__ingredient"),
        ),
    )
    required_feature = "products"
    permission_rules = {
        "list": "catalog.view",
        "retrieve": "catalog.view",
        "create": "catalog.manage",
        "partial_update": "catalog.manage",
    }
    search_fields = ("sku", "name")
    filterset_fields = ("kind", "is_active")
    ordering_fields = ("name", "sku")

    @extend_schema(request=ProductWriteSerializer, responses={201: ProductSerializer})
    def create(self, request):
        serializer = ProductWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(request.tenant, serializer.validated_data, request=request)
        product = self.get_queryset().get(pk=product.pk)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ProductWriteSerializer, responses=ProductSerializer)
    def partial_update(self, request, pk=None):
        product = self.get_object()
        serializer = ProductWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = services.update_product(
            request.tenant, product, serializer.validated_data, request=request
        )
        product = self.get_queryset().get(pk=product.pk)
        return Response(ProductSerializer(product).data)


class RecipeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = RecipeSerializer
    queryset = Recipe.objects.select_related("output_item", "product").prefetch_related("lines__ingredient")
    required_feature = "recipes"
    permission_rules = {
        "list": "catalog.view",
        "retrieve": "catalog.view",
        "create": "catalog.manage",
    }
    filterset_fields = ("output_item", "is_active")
    ordering_fields = ("effective_from", "version")

    @extend_schema(request=RecipeWriteSerializer, responses={201: RecipeSerializer})
    def create(self, request):
        serializer = RecipeWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipe = services.create_recipe(request.tenant, serializer.validated_data, request=request)
        recipe = self.get_queryset().get(pk=recipe.pk)
        return Response(RecipeSerializer(recipe).data, status=status.HTTP_201_CREATED)
