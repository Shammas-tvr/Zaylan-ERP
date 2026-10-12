import pytest

from apps.access_control.models import AssignmentScope
from tests.factories import add_branch, api_client, create_member, tenant_ctx


@pytest.mark.django_db
class TestRolePermissions:
    def test_cashier_cannot_see_members_or_organization_settings_write(self, owner):
        ctx = tenant_ctx(owner["user"], owner["organization"])
        branch = add_branch(ctx, "B1")
        cashier = create_member(
            owner["organization"], email="c@acme.test", role_key="cashier", branches=[branch]
        )
        client = api_client(cashier["user"], organization=owner["organization"])
        assert client.get("/api/v1/organization/").status_code == 200
        assert (
            client.patch("/api/v1/organization/", {"legal_name": "Nope"}, format="json").status_code
            == 403
        )
        assert client.get("/api/v1/organization/members").status_code == 403
        assert client.get("/api/v1/audit-events/").status_code == 403
        assert (
            client.post("/api/v1/branches/", {"code": "X", "name": "X"}, format="json").status_code
            == 403
        )

    def test_branch_manager_sees_only_assigned_branch(self, owner):
        ctx = tenant_ctx(owner["user"], owner["organization"])
        b1 = add_branch(ctx, "B1")
        b2 = add_branch(ctx, "B2")
        manager = create_member(
            owner["organization"],
            email="m@acme.test",
            role_key="branch_manager",
            branches=[b1],
        )
        client = api_client(manager["user"], organization=owner["organization"])
        listing = client.get("/api/v1/branches/")
        ids = {row["id"] for row in listing.data["results"]}
        assert str(b1.pk) in ids
        assert str(b2.pk) not in ids
        assert client.get(f"/api/v1/branches/{b2.pk}").status_code == 404

    def test_investor_is_read_only(self, owner):
        investor = create_member(
            owner["organization"],
            email="i@acme.test",
            role_key="investor",
            scope=AssignmentScope.TENANT,
        )
        client = api_client(investor["user"], organization=owner["organization"])
        assert client.get("/api/v1/organization/").status_code == 200
        assert (
            client.patch(
                "/api/v1/organization/", {"legal_name": "Investor Inc"}, format="json"
            ).status_code
            == 403
        )
        assert client.get("/api/v1/organization/members").status_code == 403

    def test_platform_admin_cannot_read_tenant_records_by_default(self, admin, owner):
        client = api_client(admin, organization=owner["organization"])
        response = client.get("/api/v1/organization/")
        assert response.status_code == 403

    def test_tenant_owner_cannot_call_platform_apis(self, owner):
        client = api_client(owner["user"])
        assert client.get("/api/v1/platform/tenants").status_code == 403
        assert client.get("/api/v1/platform/metrics").status_code == 403
        assert client.get("/api/v1/platform/plans").status_code == 403

    def test_cannot_grant_permissions_the_actor_does_not_hold(self, owner):
        ctx = tenant_ctx(owner["user"], owner["organization"])
        branch = add_branch(ctx, "B1")
        manager = create_member(
            owner["organization"],
            email="m@acme.test",
            role_key="branch_manager",
            branches=[branch],
        )
        client = api_client(manager["user"], organization=owner["organization"])
        response = client.post(
            "/api/v1/organization/roles",
            {
                "name": "Super",
                "permission_codes": ["organization.manage", "roles.manage"],
            },
            format="json",
        )
        assert response.status_code == 403

    def test_undeclared_action_is_denied(self, owner):
        client = api_client(owner["user"], organization=owner["organization"])
        # DELETE is not a declared branch action.
        ctx = tenant_ctx(owner["user"], owner["organization"])
        branch = add_branch(ctx, "B1")
        assert client.delete(f"/api/v1/branches/{branch.pk}").status_code == 403
