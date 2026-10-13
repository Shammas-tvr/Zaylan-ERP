from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ItemViewSet, ProductViewSet, RecipeViewSet

router = DefaultRouter()
router.register("items", ItemViewSet, basename="catalog-items")
router.register("products", ProductViewSet, basename="catalog-products")
router.register("recipes", RecipeViewSet, basename="catalog-recipes")

urlpatterns = [path("", include(router.urls))]
