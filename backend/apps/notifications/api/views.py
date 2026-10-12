from drf_spectacular.utils import extend_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.tenancy.api.base import TenantAPIView, TenantScopedViewSet

from ..models import Notification
from .. import services
from .serializers import (
    BrandNotificationSettingsSerializer,
    BrandNotificationSettingsWriteSerializer,
    NotificationSerializer,
    UnreadCountSerializer,
)


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    permission_rules = {
        "list": None,
        "retrieve": None,
        "mark_read": None,
        "mark_all_read": None,
        "unread_count": None,
    }
    ordering_fields = ("created_at",)

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @extend_schema(responses=NotificationSerializer)
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = services.mark_notification_read(request.tenant, self.get_object())
        return Response(NotificationSerializer(notification).data)

    @extend_schema(responses=UnreadCountSerializer)
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        services.mark_all_notifications_read(request.tenant)
        unread = Notification.objects.filter(
            organization=request.tenant.organization, user=request.user, read_at__isnull=True
        ).count()
        return Response({"unread_count": unread})

    @extend_schema(responses=UnreadCountSerializer)
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        unread = self.get_queryset().filter(read_at__isnull=True).count()
        return Response({"unread_count": unread})


class BrandNotificationSettingsView(TenantAPIView):
    permission_rules = {
        "get": "organization.view",
        "patch": "organization.manage",
    }

    @extend_schema(responses=BrandNotificationSettingsSerializer)
    def get(self, request):
        row = services.get_or_create_settings(request.tenant.organization)
        return Response(BrandNotificationSettingsSerializer(row).data)

    @extend_schema(
        request=BrandNotificationSettingsWriteSerializer,
        responses=BrandNotificationSettingsSerializer,
    )
    def patch(self, request):
        serializer = BrandNotificationSettingsWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        row = services.update_notification_settings(
            request.tenant, serializer.validated_data, request=request
        )
        return Response(BrandNotificationSettingsSerializer(row).data)
