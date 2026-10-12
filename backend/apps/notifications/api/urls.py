from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BrandNotificationSettingsView, NotificationViewSet

router = DefaultRouter()
router.register("", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("settings", BrandNotificationSettingsView.as_view(), name="notification-settings"),
    path("", include(router.urls)),
]
