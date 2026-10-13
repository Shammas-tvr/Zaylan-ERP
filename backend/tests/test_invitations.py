from datetime import timedelta

import pytest
from django.utils import timezone

from apps.access_control.models import AssignmentScope, Role
from apps.tenancy.models import InvitationStatus, OrganizationInvitation
from apps.tenancy.services.invitations import hash_token, invite_member
from tests.factories import ORIGIN, PASSWORD, api_client, create_user, tenant_ctx


@pytest.mark.django_db
class TestInvitations:
    def _invite(self, owner, email="new@acme.test"):
        ctx = tenant_ctx(owner["user"], owner["organization"])
        role = Role.objects.get(organization=owner["organization"], key="cashier")
        return invite_member(
            ctx,
            email=email,
            assignments=[{"role": role, "scope": AssignmentScope.BRANCHES}],
            branches=[],
        )

    def test_lookup_does_not_leak_invalid_tokens(self, client, owner):
        invitation, raw = self._invite(owner)
        missing = client.post(
            "/api/v1/auth/invitations/lookup", {"token": "not-a-real-token"}, format="json"
        )
        replay_after_accept = None
        client.post(
            "/api/v1/auth/invitations/accept",
            {"token": raw, "full_name": "New Person", "password": PASSWORD},
            format="json",
            HTTP_ORIGIN=ORIGIN,
        )
        replay_after_accept = client.post(
            "/api/v1/auth/invitations/lookup", {"token": raw}, format="json"
        )
        assert missing.status_code == 400
        assert replay_after_accept.status_code == 400
        assert missing.data["error"]["code"] == replay_after_accept.data["error"]["code"]
        assert invitation.email not in str(missing.data)

    def test_expired_invitation_cannot_be_accepted(self, client, owner):
        invitation, raw = self._invite(owner)
        OrganizationInvitation.objects.filter(pk=invitation.pk).update(
            expires_at=timezone.now() - timedelta(hours=1)
        )
        response = client.post(
            "/api/v1/auth/invitations/accept",
            {"token": raw, "full_name": "Late", "password": PASSWORD},
            format="json",
            HTTP_ORIGIN=ORIGIN,
        )
        assert response.status_code == 400

    def test_existing_user_must_sign_in_to_accept(self, client, owner):
        create_user("taken@acme.test")
        _, raw = self._invite(owner, email="taken@acme.test")
        response = client.post(
            "/api/v1/auth/invitations/accept",
            {"token": raw, "full_name": "Taken", "password": PASSWORD},
            format="json",
            HTTP_ORIGIN=ORIGIN,
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "invitation_requires_login"

    def test_token_is_hashed_at_rest(self, owner):
        invitation, raw = self._invite(owner)
        invitation.refresh_from_db()
        assert invitation.token_hash == hash_token(raw)
        assert raw not in invitation.token_hash
        assert invitation.status == InvitationStatus.PENDING

    def test_brand_admin_login_gets_session(self, client, tenant):
        """Brand Admin is created at onboard (no invite token); email login opens the brand."""
        from tests.factories import login

        response = login(client, tenant["owner_email"])
        assert response.status_code == 200
        assert response.data["user"]["email"] == tenant["owner_email"]
        assert "zaylan_refresh" in response.cookies
        auth = api_client()
        auth.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}",
            HTTP_X_ORGANIZATION_ID=str(tenant["organization"].pk),
        )
        me = auth.get("/api/v1/me/context")
        assert me.status_code == 200
        assert "organization.manage" in me.data["tenant_permissions"]
