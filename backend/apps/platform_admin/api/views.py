from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.access_control.permissions import PlatformPermission
from apps.audit_logs.api.filters import AuditEventFilter
from apps.audit_logs.api.serializers import AuditEventSerializer
from apps.audit_logs.models import AuditEvent
from apps.audit_logs.services import record_event
from apps.branches.models import Branch
from apps.subscriptions.models import Feature, OrganizationSubscription, Plan, PlanEntitlement
from apps.subscriptions.services import change_subscription
from apps.tenancy.models import MembershipStatus, Organization, OrganizationMembership
from apps.tenancy.services.invitations import invitation_url
from apps.tenancy.services.organizations import change_organization_status, onboard_organization

from .serializers import (
    FeatureSerializer,
    PlanEntitlementsInputSerializer,
    PlanSerializer,
    PlatformMetricsSerializer,
    TenantDetailSerializer,
    TenantOnboardedSerializer,
    TenantOnboardSerializer,
    TenantSerializer,
    TenantStatusSerializer,
    TenantSubscriptionUpdateSerializer,
)


class PlatformViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, PlatformPermission]
    lookup_value_regex = "[0-9a-fA-F-]{36}"


class TenantViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, PlatformViewSet):
    queryset = Organization.objects.select_related("subscription__plan")
    platform_rules = {
        "list": "platform.tenants.view",
        "retrieve": "platform.tenants.view",
        "create": "platform.tenants.manage",
        "set_status": "platform.tenants.manage",
        "set_subscription": "platform.tenants.manage",
    }
    search_fields = ("name", "slug")
    filterset_fields = ("status", "industry", "onboarding_status")
    ordering_fields = ("name", "created_at")

    def get_serializer_class(self):
        return TenantDetailSerializer if self.action == "retrieve" else TenantSerializer

    @extend_schema(request=TenantOnboardSerializer, responses={201: TenantOnboardedSerializer})
    def create(self, request):
        serializer = TenantOnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization, raw_token = onboard_organization(
            actor=request.user,
            name=data["name"],
            slug=data["slug"],
            industry=data["industry"],
            currency=data["currency"],
            timezone_name=data["timezone"],
            country=data["country"],
            locale=data["locale"],
            plan=data["plan_code"],
            owner_email=data["owner_email"],
            request=request,
        )
        organization = self.get_queryset().get(pk=organization.pk)
        return Response(
            {
                "tenant": TenantSerializer(organization).data,
                "owner_invitation_url": invitation_url(raw_token),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=TenantStatusSerializer, responses=TenantDetailSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        serializer = TenantStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_organization_status(
            actor=request.user,
            organization=self.get_object(),
            status=serializer.validated_data["status"],
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(TenantDetailSerializer(self.get_object()).data)

    @extend_schema(request=TenantSubscriptionUpdateSerializer, responses=TenantDetailSerializer)
    @action(detail=True, methods=["patch"], url_path="subscription")
    def set_subscription(self, request, pk=None):
        serializer = TenantSubscriptionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        change_subscription(
            actor=request.user,
            subscription=self.get_object().subscription,
            plan=data.get("plan_code"),
            status=data.get("status"),
            trial_ends_at=data.get("trial_ends_at"),
            request=request,
        )
        return Response(TenantDetailSerializer(self.get_object()).data)


class PlanViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    PlatformViewSet,
):
    serializer_class = PlanSerializer
    queryset = Plan.objects.prefetch_related("entitlements__feature").annotate(
        tenant_count=Count("subscriptions")
    )
    pagination_class = None
    platform_rules = {
        "list": "platform.plans.view",
        "retrieve": "platform.plans.view",
        "create": "platform.plans.manage",
        "partial_update": "platform.plans.manage",
        "set_entitlements": "platform.plans.manage",
    }
    http_method_names = ["get", "post", "patch", "put"]

    def perform_create(self, serializer):
        plan = serializer.save()
        record_event(
            action="platform.plan_created",
            actor=self.request.user,
            target=plan,
            metadata=serializer.validated_data,
            request=self.request,
        )

    def perform_update(self, serializer):
        plan = serializer.save()
        record_event(
            action="platform.plan_updated",
            actor=self.request.user,
            target=plan,
            metadata=serializer.validated_data,
            request=self.request,
        )

    def update(self, request, *args, **kwargs):
        if not kwargs.get("partial"):
            return self.http_method_not_allowed(request)
        return super().update(request, *args, **kwargs)

    @extend_schema(request=PlanEntitlementsInputSerializer, responses=PlanSerializer)
    @action(detail=True, methods=["put"], url_path="entitlements")
    def set_entitlements(self, request, pk=None):
        plan = self.get_object()
        serializer = PlanEntitlementsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            PlanEntitlement.objects.filter(plan=plan).delete()
            PlanEntitlement.objects.bulk_create(
                [
                    PlanEntitlement(
                        plan=plan,
                        feature=item["feature"],
                        enabled=item.get("enabled", True),
                        limit_value=item.get("limit_value") if item["feature"].is_limit else None,
                    )
                    for item in serializer.validated_data["entitlements"]
                ]
            )
            record_event(
                action="platform.plan_entitlements_changed",
                actor=request.user,
                target=plan,
                metadata={
                    item["feature"].code: {
                        "enabled": item.get("enabled", True),
                        "limit": item.get("limit_value"),
                    }
                    for item in serializer.validated_data["entitlements"]
                },
                request=request,
            )
        return Response(PlanSerializer(self.get_queryset().get(pk=plan.pk)).data)


class FeatureListView(APIView):
    permission_classes = [IsAuthenticated, PlatformPermission]
    platform_rules = {"get": "platform.plans.view"}

    @extend_schema(responses=FeatureSerializer(many=True))
    def get(self, request):
        return Response(FeatureSerializer(Feature.objects.all(), many=True).data)


class PlatformMetricsView(APIView):
    """Aggregated operational counts only; no tenant financial or customer data."""

    permission_classes = [IsAuthenticated, PlatformPermission]
    platform_rules = {"get": "platform.metrics.view"}

    @extend_schema(responses=PlatformMetricsSerializer)
    def get(self, request):
        def counts(queryset, field):
            return {row[field]: row["n"] for row in queryset.values(field).annotate(n=Count("pk"))}

        return Response(
            {
                "tenants_by_status": counts(Organization.objects.all(), "status"),
                "subscriptions_by_status": counts(OrganizationSubscription.objects.all(), "status"),
                "tenants_by_plan": counts(OrganizationSubscription.objects.all(), "plan__code"),
                "total_branches": Branch.objects.count(),
                "total_active_members": OrganizationMembership.objects.filter(
                    status=MembershipStatus.ACTIVE
                ).count(),
            }
        )


class PlatformAuditViewSet(mixins.ListModelMixin, PlatformViewSet):
    """Platform-level events only; tenant-internal activity stays in the tenant's own audit log."""

    serializer_class = AuditEventSerializer
    queryset = AuditEvent.objects.filter(
        Q(organization__isnull=True) | Q(action__startswith="platform.")
    ).select_related("branch")
    platform_rules = {"list": "platform.audit.view"}
    filterset_class = AuditEventFilter
