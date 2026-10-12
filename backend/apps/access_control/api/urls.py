from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import PermissionCatalogView, RoleViewSet

router = SimpleRouter(trailing_slash=False)
router.register("roles", RoleViewSet, basename="role")

urlpatterns = [
    path("permissions", PermissionCatalogView.as_view(), name="permission-catalog"),
    *router.urls,
]
