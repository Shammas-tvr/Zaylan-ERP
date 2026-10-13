from rest_framework import serializers

from apps.access_control.models import AssignmentScope
from apps.accounts.api.serializers import UserSerializer
from apps.core.validators import normalize_email

from ..models import (
    Organization,
    OrganizationBranding,
    OrganizationInvitation,
    OrganizationMembership,
)


class BrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationBranding
        fields = (
            "display_name",
            "logo_url",
            "primary_color",
            "secondary_color",
            "background_color",
            "surface_color",
            "text_color",
        )


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "slug",
            "name",
            "legal_name",
            "industry",
            "status",
            "currency",
            "timezone",
            "locale",
            "country",
            "tax_registration_number",
            "prices_include_tax",
            "contact_email",
            "contact_phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "onboarding_status",
            "created_at",
        )
        read_only_fields = ("id", "slug", "status", "onboarding_status", "created_at")


class OrganizationSummarySerializer(serializers.ModelSerializer):
    branding = BrandingSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = ("id", "slug", "name", "industry", "status", "branding")
        read_only_fields = fields


class MyOrganizationSerializer(serializers.ModelSerializer):
    organization = OrganizationSummarySerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ("id", "organization", "is_owner", "status", "joined_at")
        read_only_fields = fields


class RoleAssignmentReadSerializer(serializers.Serializer):
    role_id = serializers.UUIDField(source="role.id")
    role_name = serializers.CharField(source="role.name")
    scope = serializers.CharField()


class BranchRefSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="branch.id")
    code = serializers.CharField(source="branch.code")
    name = serializers.CharField(source="branch.name")


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    roles = RoleAssignmentReadSerializer(source="role_assignments", many=True, read_only=True)
    branches = BranchRefSerializer(source="branch_access", many=True, read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ("id", "user", "status", "is_owner", "joined_at", "roles", "branches")
        read_only_fields = fields


class MembershipStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=OrganizationMembership._meta.get_field("status").choices
    )


class StaffCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, min_length=3)
    password = serializers.CharField(max_length=128, min_length=6, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    role_id = serializers.UUIDField()
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)


class RoleAssignmentInputSerializer(serializers.Serializer):
    role_id = serializers.UUIDField()
    scope = serializers.ChoiceField(choices=AssignmentScope.choices)


class MemberRolesInputSerializer(serializers.Serializer):
    assignments = RoleAssignmentInputSerializer(many=True)


class MemberBranchesInputSerializer(serializers.Serializer):
    branch_ids = serializers.ListField(child=serializers.UUIDField(), max_length=500)


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = UserSerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvitation
        fields = (
            "id",
            "email",
            "status",
            "is_owner",
            "role_assignments",
            "branch_ids",
            "invited_by",
            "expires_at",
            "accepted_at",
            "created_at",
            "is_expired",
        )
        read_only_fields = fields

    def get_is_expired(self, invitation) -> bool:
        from django.utils import timezone

        return invitation.expires_at <= timezone.now()


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    assignments = RoleAssignmentInputSerializer(many=True, allow_empty=False)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)

    def validate_email(self, value: str) -> str:
        return normalize_email(value)


class InvitationCreatedSerializer(serializers.Serializer):
    invitation = InvitationSerializer()
    invitation_url = serializers.CharField()


class InvitationTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)


class InvitationLookupResultSerializer(serializers.Serializer):
    organization_name = serializers.CharField()
    email = serializers.EmailField()
    account_exists = serializers.BooleanField()
    expires_at = serializers.DateTimeField()


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    password = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default="", trim_whitespace=False
    )


class BranchAccessSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())


class EntitlementSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    limit = serializers.IntegerField(allow_null=True)


class TenantContextSerializer(serializers.Serializer):
    organization = OrganizationSerializer()
    branding = BrandingSerializer()
    membership = serializers.DictField()
    tenant_permissions = serializers.ListField(child=serializers.CharField())
    branches = BranchAccessSerializer(many=True)
    entitlements = serializers.DictField(child=EntitlementSerializer())


class PermissionsSerializer(serializers.Serializer):
    tenant_permissions = serializers.ListField(child=serializers.CharField())
    branch_permissions = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )


class SubscriptionSummarySerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    plan_name = serializers.CharField()
    status = serializers.CharField()
    trial_ends_at = serializers.DateTimeField(allow_null=True)
    current_period_end = serializers.DateTimeField(allow_null=True)
    entitlements = serializers.DictField(child=EntitlementSerializer())
    usage = serializers.DictField(child=serializers.IntegerField())
