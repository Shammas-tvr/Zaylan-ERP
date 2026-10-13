from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ItemViewSet, RecipeViewSet

router = DefaultRouter()
router.register("items", ItemViewSet, basename="catalog-items")
router.register("recipes", RecipeViewSet, basename="catalog-recipes")

urlpatterns = [path("", include(router.urls))]
