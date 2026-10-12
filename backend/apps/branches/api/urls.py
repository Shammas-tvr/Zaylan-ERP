from rest_framework.routers import SimpleRouter

from .views import BranchViewSet

router = SimpleRouter(trailing_slash=False)
router.register("", BranchViewSet, basename="branch")

urlpatterns = router.urls
