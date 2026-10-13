import uuid

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.access_control.models import AssignmentScope, MembershipRoleAssignment, Role
from apps.access_control.services import grant_platform_role, sync_permission_catalog
from apps.branches.models import MembershipBranchAccess
from apps.branches.services import create_branch
from apps.subscriptions.models import Plan
from apps.subscriptions.services import ensure_default_plans
from apps.tenancy.context import TenantContext, resolve_tenant_context
from apps.tenancy.models import MembershipStatus, OrganizationMembership
from apps.tenancy.services.organizations import onboard_organization

ORIGIN = "http://localhost:5173"
PASSWORD = "CorrectHorse-9x"


def bootstrap_catalogs() -> None:
    sync_permission_catalog()
    ensure_default_plans()


def plan(code: str = "growth") -> Plan:
    return Plan.objects.get(code=code)


def create_user(email: str, *, name: str | None = None, password: str = PASSWORD):
    return get_user_model().objects.create_user(
        email=email, password=password, full_name=name or email.split("@")[0].title()
    )


def platform_admin(email: str = "platform@zaylan.test"):
    user = create_user(email, name="Platform Admin")
    grant_platform_role(user=user, role_key="platform_super_admin")
    return user


def create_tenant(
    *,
    slug: str = "acme",
    name: str | None = None,
    owner_email: str | None = None,
    plan_code: str = "growth",
    owner_password: str = PASSWORD,
) -> dict:
    email = owner_email or f"owner@{slug}.test"
    organization = onboard_organization(
        actor=None,
        name=name or slug.title(),
        slug=slug,
        industry="RETAIL",
        currency="INR",
        timezone_name="Asia/Kolkata",
        country="IN",
        locale="en-IN",
        plan=plan(plan_code),
        owner_email=email,
        owner_password=owner_password,
        owner_full_name="Owner",
    )
    membership = OrganizationMembership.objects.select_related("user").get(
        organization=organization, is_owner=True
    )
    return {
        "organization": organization,
        "owner_email": email,
        "user": membership.user,
        "membership": membership,
    }


def accept_owner(tenant: dict, email: str | None = None) -> dict:
    """Compatibility helper: brand admin is created during onboard now."""
    membership = tenant.get("membership") or OrganizationMembership.objects.select_related(
        "user"
    ).get(organization=tenant["organization"], is_owner=True)
    user = tenant.get("user") or membership.user
    assert user.email == (email or tenant["owner_email"])
    return {"user": user, "membership": membership, "organization": membership.organization}


def role(organization, key: str) -> Role:
    return Role.objects.get(organization=organization, key=key)


def create_member(
    organization,
    *,
    email: str,
    role_key: str = "cashier",
    scope: str = AssignmentScope.BRANCHES,
    branches=(),
    password: str = PASSWORD,
):
    user = create_user(email)
    membership = OrganizationMembership.objects.create(
        organization=organization, user=user, status=MembershipStatus.ACTIVE
    )
    MembershipRoleAssignment.objects.create(
        organization=organization,
        membership=membership,
        role=role(organization, role_key),
        scope=scope,
    )
    for branch in branches:
        MembershipBranchAccess.objects.create(
            organization=organization, membership=membership, branch=branch
        )
    return {"user": user, "membership": membership}


class DummyCtx:
    """Minimal context for services that only need organization/user/membership/entitlements."""

    def __init__(self, organization, user, membership, entitlements=None):
        self.organization = organization
        self.user = user
        self.membership = membership
        self.entitlements = entitlements or {}


def tenant_ctx(user, organization) -> TenantContext:
    return resolve_tenant_context(user, str(organization.pk))


def add_branch(ctx_or_org, code: str, name: str | None = None):
    if hasattr(ctx_or_org, "organization"):
        ctx = ctx_or_org
    else:
        # Platform-created branch without a real actor uses a synthetic owner context.
        membership = (
            OrganizationMembership.objects.filter(organization=ctx_or_org, is_owner=True)
            .select_related("user")
            .first()
        )
        ctx = tenant_ctx(membership.user, ctx_or_org)
    return create_branch(ctx, {"code": code, "name": name or code.title()})


def access_token(user) -> str:
    return str(RefreshToken.for_user(user).access_token)


def api_client(user=None, *, organization=None, origin: str = ORIGIN) -> APIClient:
    client = APIClient()
    extra = {"HTTP_ORIGIN": origin}
    if user is not None:
        extra["HTTP_AUTHORIZATION"] = f"Bearer {access_token(user)}"
    if organization is not None:
        extra["HTTP_X_ORGANIZATION_ID"] = str(organization.pk)
    client.credentials(**extra)
    return client


def login(client: APIClient, email: str, password: str = PASSWORD, origin: str = ORIGIN):
    return client.post(
        "/api/v1/auth/login",
        {"identifier": email, "password": password},
        format="json",
        HTTP_ORIGIN=origin,
    )


def org_url(path: str) -> str:
    return f"/api/v1/{path.lstrip('/')}"


def foreign_uuid() -> str:
    return str(uuid.uuid4())
