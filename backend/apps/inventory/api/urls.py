from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdjustmentView, BalanceView, LocationView, MovementView, ProductionViewSet, TransferViewSet

router = DefaultRouter()
router.register("production", ProductionViewSet, basename="production")
router.register("transfers", TransferViewSet, basename="transfers")

urlpatterns = [
    path("locations", LocationView.as_view(), name="inventory-locations"),
    path("balances", BalanceView.as_view(), name="inventory-balances"),
    path("movements", MovementView.as_view(), name="inventory-movements"),
    path("adjustments", AdjustmentView.as_view(), name="inventory-adjustments"),
    path("", include(router.urls)),
]
