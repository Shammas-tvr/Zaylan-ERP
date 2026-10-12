"""Platform serializers expose tenant lifecycle and usage metadata, never tenant business data."""

from rest_framework import serializers

from apps.core.validators import normalize_email
from apps.subscriptions.models import Feature, Plan, PlanEntitlement, SubscriptionStatus
from apps.tenancy.models import Industry, Organization, OrganizationStatus


class TenantSubscriptionSerializer(serializers.Serializer):
    plan_code = serializers.CharField(source="plan.code")
    plan_name = serializers.CharField(source="plan.name")
    status = serializers.CharField()
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    current_period_end = serializers.DateTimeField(allow_null=True)


class TenantSerializer(serializers.ModelSerializer):
    subscription = TenantSubscriptionSerializer(read_only=True, allow_null=True)
    usage = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = (
            "id",
            "slug",
            "name",
            "legal_name",
            "industry",
            "status",
            "status_reason",
            "onboarding_status",
            "currency",
            "timezone",
            "country",
            "contact_email",
            "contact_phone",
            "created_at",
            "activated_at",
            "suspended_at",
            "deactivated_at",
            "subscription",
            "usage",
        )
        read_only_fields = fields

    def get_usage(self, organization) -> dict[str, int]:
        usage = getattr(organization, "_prefetched_usage", None)
        if usage is not None:
            return usage
        from apps.subscriptions.services import organization_usage

        return organization_usage(organization)


class TenantDetailSerializer(TenantSerializer):
    class Meta(TenantSerializer.Meta):
        fields = TenantSerializer.Meta.fields
        read_only_fields = fields


class TenantOnboardSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    slug = serializers.SlugField(max_length=63, min_length=3)
    industry = serializers.ChoiceField(choices=Industry.choices)
    currency = serializers.RegexField(r"^[A-Z]{3}$", default="INR")
    timezone = serializers.CharField(max_length=64, default="Asia/Kolkata")
    country = serializers.RegexField(r"^[A-Z]{2}$", default="IN")
    locale = serializers.CharField(max_length=16, default="en-IN")
    legal_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    plan_code = serializers.SlugField()
    owner_email = serializers.EmailField(max_length=254)

    def validate_owner_email(self, value: str) -> str:
        return normalize_email(value)

    def validate_contact_email(self, value: str) -> str:
        return normalize_email(value) if value else ""

    def validate_plan_code(self, value: str) -> Plan:
        plan = Plan.objects.filter(code=value, is_active=True).first()
        if plan is None:
            raise serializers.ValidationError("Unknown or inactive plan.")
        return plan


class TenantOnboardedSerializer(serializers.Serializer):
    tenant = TenantSerializer()
    owner_invitation_url = serializers.CharField()
    invitation_email_sent = serializers.BooleanField()


class TenantStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrganizationStatus.choices)
    reason = serializers.CharField(max_length=500)


class TenantSubscriptionUpdateSerializer(serializers.Serializer):
    plan_code = serializers.SlugField(required=False)
    status = serializers.ChoiceField(choices=SubscriptionStatus.choices, required=False)
    trial_ends_at = serializers.DateTimeField(required=False)

    def validate_plan_code(self, value: str) -> Plan:
        plan = Plan.objects.filter(code=value).first()
        if plan is None:
            raise serializers.ValidationError("Unknown plan.")
        return plan


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ("code", "name", "description", "is_limit")
        read_only_fields = fields


class PlanEntitlementSerializer(serializers.ModelSerializer):
    feature_code = serializers.SlugRelatedField(
        source="feature", slug_field="code", queryset=Feature.objects.all()
    )

    class Meta:
        model = PlanEntitlement
        fields = ("feature_code", "enabled", "limit_value")


class PlanSerializer(serializers.ModelSerializer):
    entitlements = PlanEntitlementSerializer(many=True, read_only=True)
    tenant_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plan
        fields = (
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "trial_days",
            "entitlements",
            "tenant_count",
        )
        read_only_fields = ("id", "entitlements", "tenant_count")


class PlanEntitlementsInputSerializer(serializers.Serializer):
    entitlements = PlanEntitlementSerializer(many=True)


class PlatformMetricsSerializer(serializers.Serializer):
    tenants_by_status = serializers.DictField(child=serializers.IntegerField())
    subscriptions_by_status = serializers.DictField(child=serializers.IntegerField())
    tenants_by_plan = serializers.DictField(child=serializers.IntegerField())
    total_branches = serializers.IntegerField()
    total_active_members = serializers.IntegerField()
    total_brands = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
