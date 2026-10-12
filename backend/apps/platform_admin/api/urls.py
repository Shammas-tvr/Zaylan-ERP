from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    FeatureListView,
    PlanViewSet,
    PlatformAuditViewSet,
    PlatformMetricsView,
    TenantViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("tenants", TenantViewSet, basename="platform-tenant")
router.register("plans", PlanViewSet, basename="platform-plan")
router.register("audit-events", PlatformAuditViewSet, basename="platform-audit-event")

urlpatterns = [
    path("features", FeatureListView.as_view(), name="platform-features"),
    path("metrics", PlatformMetricsView.as_view(), name="platform-metrics"),
    *router.urls,
]
