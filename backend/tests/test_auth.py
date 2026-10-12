import pytest
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import User
from tests.factories import ORIGIN, PASSWORD, api_client, create_user, login


@pytest.mark.django_db
class TestAuthentication:
    def test_login_issues_access_token_and_refresh_cookie(self, client):
        create_user("a@example.com")
        response = login(client, "a@example.com")
        assert response.status_code == 200
        assert "access" in response.data
        assert "password" not in str(response.data).lower()
        assert "zaylan_refresh" in response.cookies
        cookie = response.cookies["zaylan_refresh"]
        assert cookie["httponly"]
        assert cookie["path"] == "/api/v1/auth/"

    def test_login_rejects_wrong_password_without_leaking_existence(self, client):
        create_user("a@example.com")
        missing = login(client, "nobody@example.com")
        wrong = login(client, "a@example.com", "wrong-password-99")
        assert missing.status_code == wrong.status_code == 401
        assert missing.data["error"]["message"] == wrong.data["error"]["message"]

    def test_login_rejects_untrusted_origin(self, client):
        create_user("a@example.com")
        response = login(client, "a@example.com", origin="https://evil.example")
        assert response.status_code == 403

    def test_refresh_rotates_cookie_and_rejects_reuse(self, client):
        create_user("a@example.com")
        login(client, "a@example.com")
        first = client.post("/api/v1/auth/refresh", {}, format="json", HTTP_ORIGIN=ORIGIN)
        assert first.status_code == 200
        stolen = first.cookies["zaylan_refresh"].value
        second = client.post("/api/v1/auth/refresh", {}, format="json", HTTP_ORIGIN=ORIGIN)
        assert second.status_code == 200
        client.cookies["zaylan_refresh"] = stolen
        reused = client.post("/api/v1/auth/refresh", {}, format="json", HTTP_ORIGIN=ORIGIN)
        assert reused.status_code == 401
        # Every session of that user is revoked after reuse.
        client.cookies["zaylan_refresh"] = second.cookies["zaylan_refresh"].value
        after = client.post("/api/v1/auth/refresh", {}, format="json", HTTP_ORIGIN=ORIGIN)
        assert after.status_code == 401

    def test_logout_clears_cookie(self, client):
        create_user("a@example.com")
        login(client, "a@example.com")
        response = client.post("/api/v1/auth/logout", {}, format="json", HTTP_ORIGIN=ORIGIN)
        assert response.status_code == 204
        assert response.cookies["zaylan_refresh"].value == ""

    def test_me_requires_bearer_token(self, client):
        response = client.get("/api/v1/me/")
        assert response.status_code == 401

    def test_password_change_revokes_old_access_tokens(self):
        user = create_user("a@example.com")
        old_client = api_client(user)
        response = old_client.post(
            "/api/v1/auth/password/change",
            {"current_password": PASSWORD, "new_password": "NewCorrectHorse-9x"},
            format="json",
        )
        assert response.status_code == 200
        stale = api_client(user)
        token = AccessToken.for_user(user)
        token["iat"] = 1
        stale.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
        denied = stale.get("/api/v1/me/")
        assert denied.status_code == 401
        user = User.objects.get(pk=user.pk)
        assert user.check_password("NewCorrectHorse-9x")
