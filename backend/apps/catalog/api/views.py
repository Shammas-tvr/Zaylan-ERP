from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.response import Response

from apps.tenancy.api.base import TenantScopedViewSet

from .. import services
from ..models import Item, Product, Recipe
from .serializers import (
    ItemSerializer,
    ItemWriteSerializer,
    ProductSerializer,
    ProductWriteSerializer,
    RecipeSerializer,
    RecipeWriteSerializer,
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
    queryset = Product.objects.select_related("inventory_item").prefetch_related("branches")
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
