import pytest

from apps.subscriptions.models import OrganizationSubscription, PlanEntitlement, SubscriptionStatus
from tests.factories import add_branch, api_client, create_tenant, tenant_ctx


@pytest.mark.django_db
class TestSubscriptions:
    def test_starter_plan_blocks_extra_branches(self, catalogs):
        tenant = create_tenant(slug="tiny", plan_code="starter")
        from tests.factories import accept_owner

        owner = accept_owner(tenant)
        ctx = tenant_ctx(owner["user"], owner["organization"])
        add_branch(ctx, "ONLY")
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.post(
            "/api/v1/branches/", {"code": "TWO", "name": "Second"}, format="json"
        )
        assert response.status_code == 403
        assert response.data["error"]["code"] == "plan_limit_reached"

    def test_custom_roles_require_entitlement(self, catalogs):
        tenant = create_tenant(slug="tiny2", plan_code="starter")
        from tests.factories import accept_owner

        owner = accept_owner(tenant)
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.post(
            "/api/v1/organization/roles",
            {"name": "Closer", "permission_codes": ["organization.view"]},
            format="json",
        )
        assert response.status_code == 403
        assert response.data["error"]["code"] == "feature_not_available"

    def test_suspended_subscription_blocks_tenant_api(self, owner):
        OrganizationSubscription.objects.filter(organization=owner["organization"]).update(
            status=SubscriptionStatus.SUSPENDED
        )
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.get("/api/v1/organization/")
        assert response.status_code == 403
        assert response.data["error"]["code"] == "subscription_inactive"

    def test_platform_can_change_plan(self, admin, owner):
        client = api_client(admin)
        response = client.patch(
            f"/api/v1/platform/tenants/{owner['organization'].pk}/subscription",
            {"plan_code": "starter", "status": "ACTIVE"},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["subscription"]["plan_code"] == "starter"

    def test_disabled_audit_feature_blocks_log(self, owner):
        subscription = owner["organization"].subscription
        PlanEntitlement.objects.filter(plan=subscription.plan, feature__code="audit_log").update(
            enabled=False
        )
        client = api_client(owner["user"], organization=owner["organization"])
        assert client.get("/api/v1/audit-events/").status_code == 403
