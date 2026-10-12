import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.access_control.models import AssignmentScope, MembershipRoleAssignment
from apps.branches.models import MembershipBranchAccess
from tests.factories import (
    add_branch,
    api_client,
    tenant_ctx,
)


@pytest.mark.django_db
class TestTenantIsolation:
    def test_organization_header_does_not_grant_access(self, owner, other_tenant):
        client = api_client(owner["user"], organization=other_tenant["organization"])
        response = client.get("/api/v1/organization/")
        assert response.status_code == 403
        assert "error" in response.data
        assert other_tenant["organization"].name not in str(response.data)

    def test_missing_organization_header_is_rejected(self, owner):
        client = api_client(owner["user"])
        response = client.get("/api/v1/organization/")
        assert response.status_code == 400
        assert response.data["error"]["code"] == "organization_required"

    def test_unknown_organization_id_matches_inaccessible_response(self, owner, other_tenant):
        client = api_client(owner["user"], organization=owner["organization"])
        unknown = api_client(owner["user"])
        unknown.credentials(
            HTTP_AUTHORIZATION=client._credentials["HTTP_AUTHORIZATION"],
            HTTP_X_ORGANIZATION_ID=str(uuid.uuid4()),
        )
        foreign = api_client(owner["user"], organization=other_tenant["organization"])
        a = unknown.get("/api/v1/organization/")
        b = foreign.get("/api/v1/organization/")
        assert a.status_code == b.status_code == 403
        assert a.data["error"]["code"] == b.data["error"]["code"]

    def test_member_list_never_includes_another_tenant(self, owner, other_owner):
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.get("/api/v1/organization/members")
        assert response.status_code == 200
        emails = {row["user"]["email"] for row in response.data["results"]}
        assert other_owner["user"].email not in emails
        assert owner["user"].email in emails

    def test_foreign_member_id_is_404(self, owner, other_owner):
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.get(f"/api/v1/organization/members/{other_owner['membership'].pk}")
        assert response.status_code == 404

    def test_foreign_branch_id_is_404(self, owner, other_owner):
        other_ctx = tenant_ctx(other_owner["user"], other_owner["organization"])
        foreign_branch = add_branch(other_ctx, "B1")
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.get(f"/api/v1/branches/{foreign_branch.pk}")
        assert response.status_code == 404

    def test_search_cannot_find_foreign_branch(self, owner, other_owner):
        other_ctx = tenant_ctx(other_owner["user"], other_owner["organization"])
        add_branch(other_ctx, "SECRET", "Secret Kitchen")
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.get("/api/v1/branches/?search=Secret")
        assert response.status_code == 200
        assert response.data["results"] == []

    def test_spoofed_organization_in_body_is_ignored(self, owner, other_tenant):
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.post(
            "/api/v1/branches/",
            {
                "code": "HQ",
                "name": "Headquarters",
                "organization": str(other_tenant["organization"].pk),
            },
            format="json",
        )
        assert response.status_code == 201
        assert response.data["code"] == "HQ"
        from apps.branches.models import Branch

        branch = Branch.objects.get(pk=response.data["id"])
        assert branch.organization_id == owner["organization"].pk

    def test_composite_fk_rejects_cross_tenant_branch_access(self, owner, other_owner):
        ctx = tenant_ctx(owner["user"], owner["organization"])
        branch = add_branch(ctx, "A1")
        with pytest.raises(IntegrityError), transaction.atomic():
            MembershipBranchAccess.objects.create(
                organization=other_owner["organization"],
                membership=owner["membership"],
                branch=branch,
            )

    def test_composite_fk_rejects_cross_tenant_role_assignment(self, owner, other_owner):
        from apps.access_control.models import Role

        foreign_role = Role.objects.get(organization=other_owner["organization"], key="cashier")
        with pytest.raises(IntegrityError), transaction.atomic():
            MembershipRoleAssignment.objects.create(
                organization=owner["organization"],
                membership=owner["membership"],
                role=foreign_role,
                scope=AssignmentScope.TENANT,
            )

    def test_audit_log_is_tenant_scoped(self, owner, other_owner):
        other_client = api_client(other_owner["user"], organization=other_owner["organization"])
        other_client.patch("/api/v1/organization/", {"legal_name": "Beta Foods"}, format="json")
        client = api_client(owner["user"], organization=owner["organization"])
        response = client.get("/api/v1/audit-events/")
        assert response.status_code == 200
        actions = [row["action"] for row in response.data["results"]]
        assert "organization.settings_updated" not in actions
        texts = str(response.data)
        assert "Beta Foods" not in texts
        assert other_owner["user"].email not in texts
