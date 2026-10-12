from rest_framework.routers import SimpleRouter

from .views import AuditEventViewSet

router = SimpleRouter(trailing_slash=False)
router.register("", AuditEventViewSet, basename="audit-event")

urlpatterns = router.urls
