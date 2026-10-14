from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ImageUploadView, ItemViewSet, ProductViewSet, RecipeViewSet, SupplierViewSet

router = DefaultRouter()
router.register("items", ItemViewSet, basename="catalog-items")
router.register("suppliers", SupplierViewSet, basename="catalog-suppliers")
router.register("products", ProductViewSet, basename="catalog-products")
router.register("recipes", RecipeViewSet, basename="catalog-recipes")

urlpatterns = [
    path("images/", ImageUploadView.as_view(), name="catalog-images"),
    path("", include(router.urls)),
]
