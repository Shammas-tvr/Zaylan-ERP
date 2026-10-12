from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.access_control.models import MembershipRoleAssignment, Role
from apps.access_control.services import set_member_roles
from apps.accounts import services as auth_services
from apps.accounts.api.serializers import SessionSerializer
from apps.accounts.authentication import ZaylanJWTAuthentication
from apps.branches.models import Branch, MembershipBranchAccess
from apps.branches.services import resolve_branches, set_member_branch_access
from apps.core.exceptions import BusinessRuleViolation
from apps.subscriptions.services import organization_usage

from ..models import (
    InvitationStatus,
    MembershipStatus,
    OrganizationBranding,
    OrganizationInvitation,
    OrganizationMembership,
)
from ..services.invitations import (
    INVALID_INVITATION,
    accept_invitation,
    find_pending_invitation,
    invitation_url,
    invite_member,
    revoke_invitation,
)
from ..services.members import change_membership_status
from ..services.organizations import update_branding, update_organization_settings
from .base import TenantAPIView, TenantScopedViewSet
from .serializers import (
    BrandingSerializer,
    InvitationAcceptSerializer,
    InvitationCreatedSerializer,
    InvitationCreateSerializer,
    InvitationLookupResultSerializer,
    InvitationSerializer,
    InvitationTokenSerializer,
    MemberBranchesInputSerializer,
    MemberRolesInputSerializer,
    MembershipSerializer,
    MembershipStatusSerializer,
    MyOrganizationSerializer,
    OrganizationSerializer,
    PermissionsSerializer,
    SubscriptionSummarySerializer,
    TenantContextSerializer,
)


def _entitlements_payload(ctx) -> dict:
    return {
        code: {"enabled": entitlement.enabled, "limit": entitlement.limit}
        for code, entitlement in ctx.entitlements.items()
    }


def _branding(organization) -> OrganizationBranding:
    branding, _ = OrganizationBranding.objects.get_or_create(organization=organization)
    return branding


class MyOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MyOrganizationSerializer(many=True))
    def get(self, request):
        memberships = (
            OrganizationMembership.objects.filter(user=request.user, status=MembershipStatus.ACTIVE)
            .select_related("organization", "organization__branding")
            .order_by("organization__name")
        )
        return Response(MyOrganizationSerializer(memberships, many=True).data)


class MyContextView(TenantAPIView):
    permission_rules = {"get": None}

    @extend_schema(responses=TenantContextSerializer)
    def get(self, request):
        ctx = request.tenant
        branches = Branch.objects.filter(
            organization=ctx.organization, pk__in=ctx.accessible_branch_ids
        ).order_by("name")
        return Response(
            {
                "organization": OrganizationSerializer(ctx.organization).data,
                "branding": BrandingSerializer(_branding(ctx.organization)).data,
                "membership": {"id": str(ctx.membership.pk), "is_owner": ctx.membership.is_owner},
                "tenant_permissions": sorted(ctx.tenant_permissions),
                "branches": [
                    {
                        "id": branch.pk,
                        "code": branch.code,
                        "name": branch.name,
                        "status": branch.status,
                        "permissions": sorted(ctx.branch_permissions[branch.pk]),
                    }
                    for branch in branches
                ],
                "entitlements": _entitlements_payload(ctx),
            }
        )


class MyPermissionsView(TenantAPIView):
    permission_rules = {"get": None}

    @extend_schema(responses=PermissionsSerializer)
    def get(self, request):
        ctx = request.tenant
        return Response(
            {
                "tenant_permissions": sorted(ctx.tenant_permissions),
                "branch_permissions": {
                    str(branch_id): sorted(perms)
                    for branch_id, perms in ctx.branch_permissions.items()
                },
            }
        )


class OrganizationView(TenantAPIView):
    permission_rules = {"get": "organization.view", "patch": "organization.manage"}

    @extend_schema(responses=OrganizationSerializer)
    def get(self, request):
        return Response(OrganizationSerializer(request.tenant.organization).data)

    @extend_schema(request=OrganizationSerializer, responses=OrganizationSerializer)
    def patch(self, request):
        serializer = OrganizationSerializer(
            request.tenant.organization, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        organization = update_organization_settings(
            request.tenant, serializer.validated_data, request=request
        )
        return Response(OrganizationSerializer(organization).data)


class BrandingView(TenantAPIView):
    permission_rules = {"get": "organization.view", "patch": "organization.manage"}

    @extend_schema(responses=BrandingSerializer)
    def get(self, request):
        return Response(BrandingSerializer(_branding(request.tenant.organization)).data)

    @extend_schema(request=BrandingSerializer, responses=BrandingSerializer)
    def patch(self, request):
        serializer = BrandingSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        branding = update_branding(request.tenant, serializer.validated_data, request=request)
        return Response(BrandingSerializer(branding).data)


class SubscriptionView(TenantAPIView):
    permission_rules = {"get": "subscription.view"}

    @extend_schema(responses=SubscriptionSummarySerializer)
    def get(self, request):
        ctx = request.tenant
        subscription = ctx.organization.subscription
        return Response(
            {
                "plan_code": subscription.plan.code,
                "plan_name": subscription.plan.name,
                "status": subscription.status,
                "trial_ends_at": subscription.trial_ends_at,
                "current_period_end": subscription.current_period_end,
                "entitlements": _entitlements_payload(ctx),
                "usage": organization_usage(ctx.organization),
            }
        )


def _resolve_assignments(ctx, items: list[dict]) -> list[dict]:
    role_ids = {str(item["role_id"]) for item in items}
    roles = {
        str(r.pk): r for r in Role.objects.filter(organization=ctx.organization, pk__in=role_ids)
    }
    if len(roles) != len(role_ids):
        raise BusinessRuleViolation("One or more roles do not exist.")
    return [{"role": roles[str(item["role_id"])], "scope": item["scope"]} for item in items]


class MemberViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, TenantScopedViewSet):
    serializer_class = MembershipSerializer
    queryset = OrganizationMembership.objects.select_related("user")
    permission_rules = {
        "list": "members.view",
        "retrieve": "members.view",
        "set_status": "members.manage",
        "set_roles": "roles.manage",
        "set_branches": "members.manage",
    }
    branch_scoped_actions = ("list", "retrieve")
    search_fields = ("user__email", "user__full_name")
    ordering_fields = ("joined_at", "user__full_name")
    filterset_fields = ("status",)

    def get_queryset(self):
        ctx = self.request.tenant
        queryset = (
            super()
            .get_queryset()
            .prefetch_related(
                Prefetch(
                    "role_assignments",
                    queryset=MembershipRoleAssignment.objects.select_related("role"),
                ),
                Prefetch(
                    "branch_access",
                    queryset=MembershipBranchAccess.objects.select_related("branch"),
                ),
            )
        )
        if self.action in self.branch_scoped_actions and not ctx.has_permission("members.view"):
            # Branch-scoped viewers only see members assigned to the branches they manage.
            queryset = queryset.filter(
                branch_access__branch_id__in=ctx.branch_ids_with("members.view")
            ).distinct()
        return queryset

    @extend_schema(request=MembershipStatusSerializer, responses=MembershipSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        serializer = MembershipStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_membership_status(
            request.tenant, self.get_object(), serializer.validated_data["status"], request=request
        )
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(request=MemberRolesInputSerializer, responses=MembershipSerializer)
    @action(detail=True, methods=["put"], url_path="roles")
    def set_roles(self, request, pk=None):
        serializer = MemberRolesInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = self.get_object()
        assignments = _resolve_assignments(request.tenant, serializer.validated_data["assignments"])
        set_member_roles(request.tenant, membership, assignments, request=request)
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(request=MemberBranchesInputSerializer, responses=MembershipSerializer)
    @action(detail=True, methods=["put"], url_path="branches")
    def set_branches(self, request, pk=None):
        serializer = MemberBranchesInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = self.get_object()
        branches = resolve_branches(request.tenant, serializer.validated_data["branch_ids"])
        set_member_branch_access(request.tenant, membership, branches, request=request)
        return Response(self.get_serializer(self.get_object()).data)


class InvitationViewSet(mixins.ListModelMixin, TenantScopedViewSet):
    serializer_class = InvitationSerializer
    queryset = OrganizationInvitation.objects.select_related("invited_by")
    permission_rules = {
        "list": "members.manage",
        "create": "members.manage",
        "revoke": "members.manage",
    }
    filterset_fields = ("status",)

    @extend_schema(request=InvitationCreateSerializer, responses={201: InvitationCreatedSerializer})
    def create(self, request):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ctx = request.tenant
        invitation, raw_token = invite_member(
            ctx,
            email=serializer.validated_data["email"],
            assignments=_resolve_assignments(ctx, serializer.validated_data["assignments"]),
            branches=resolve_branches(ctx, serializer.validated_data["branch_ids"]),
            request=request,
        )
        return Response(
            {
                "invitation": InvitationSerializer(invitation).data,
                "invitation_url": invitation_url(raw_token),
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses=InvitationSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        revoke_invitation(request.tenant, invitation, request=request)
        invitation.refresh_from_db()
        return Response(InvitationSerializer(invitation).data)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list" and "status" not in self.request.query_params:
            queryset = queryset.filter(status=InvitationStatus.PENDING)
        return queryset


class InvitationLookupView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invitation"

    @extend_schema(request=InvitationTokenSerializer, responses=InvitationLookupResultSerializer)
    def post(self, request):
        serializer = InvitationTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = find_pending_invitation(serializer.validated_data["token"])
        if invitation is None:
            raise BusinessRuleViolation(INVALID_INVITATION, code="invitation_invalid")
        from apps.accounts.models import User

        return Response(
            {
                "organization_name": invitation.organization.name,
                "email": invitation.email,
                "account_exists": User.objects.filter(email__iexact=invitation.email).exists(),
                "expires_at": invitation.expires_at,
            }
        )


class InvitationAcceptView(APIView):
    # Authentication is optional: existing users must be signed in, new users set a password.
    authentication_classes = [ZaylanJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invitation"

    @extend_schema(request=InvitationAcceptSerializer, responses=SessionSerializer)
    def post(self, request):
        if not auth_services.is_trusted_origin(request):
            raise PermissionDenied("Request origin is not allowed.")
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        membership, user, _ = accept_invitation(
            serializer.validated_data["token"],
            authenticated_user=user,
            full_name=serializer.validated_data["full_name"],
            password=serializer.validated_data["password"],
            request=request,
        )
        from apps.accounts.api.serializers import MeSerializer

        access, refresh = auth_services.issue_tokens(user)
        response = Response(
            {
                "access": access,
                "user": MeSerializer(user).data,
                "organization_id": str(membership.organization_id),
            }
        )
        auth_services.set_refresh_cookie(response, refresh)
        return response
