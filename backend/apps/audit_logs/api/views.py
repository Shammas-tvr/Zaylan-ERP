from rest_framework import mixins

from apps.tenancy.api.base import TenantScopedViewSet

from ..models import AuditEvent
from .filters import AuditEventFilter
from .serializers import AuditEventSerializer


class AuditEventViewSet(mixins.ListModelMixin, TenantScopedViewSet):
    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.select_related("branch")
    permission_rules = {"list": "audit.view"}
    required_feature = "audit_log"
    filterset_class = AuditEventFilter
    ordering_fields = ("occurred_at",)
