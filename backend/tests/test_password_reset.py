import re

import pytest
from django.core import mail

from apps.accounts.models import PasswordResetOTP
from apps.accounts.services import mask_email
from tests.factories import ORIGIN, PASSWORD, create_tenant, login, platform_admin


@pytest.fixture(autouse=True)
def _password_reset_throttle(settings):
    rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "auth_password_reset": "100/min"}
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}


@pytest.mark.django_db
def test_mask_email_hides_middle_letters():
    assert mask_email("admin@otpco.test") == "a***n@otpco.test"
    assert mask_email("ab@x.test") == "a***@x.test"


@pytest.mark.django_db
def test_brand_portal_returns_name_and_masked_email(client, catalogs):
    create_tenant(slug="otpco", name="OTP Co", owner_email="admin@otpco.test")
    response = client.get("/api/v1/auth/brands/otpco/portal")
    assert response.status_code == 200
    assert response.data["name"] == "OTP Co"
    assert response.data["slug"] == "otpco"
    assert response.data["masked_admin_email"] == "a***n@otpco.test"
    assert "admin@otpco.test" not in str(response.data)


@pytest.mark.django_db
def test_brand_admin_can_reset_password_with_slug_otp(client, settings, catalogs):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    tenant = create_tenant(slug="otpco", owner_email="admin@otpco.test")

    forgot = client.post(
        "/api/v1/auth/password/forgot",
        {"slug": "otpco"},
        format="json",
        HTTP_ORIGIN=ORIGIN,
    )
    assert forgot.status_code == 200
    assert len(mail.outbox) == 1
    match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
    assert match, mail.outbox[0].body
    code = match.group(1)

    reset = client.post(
        "/api/v1/auth/password/reset",
        {
            "slug": "otpco",
            "otp": code,
            "new_password": "NewPass-42",
        },
        format="json",
        HTTP_ORIGIN=ORIGIN,
    )
    assert reset.status_code == 200, reset.data

    old = login(client, "admin@otpco.test", PASSWORD)
    assert old.status_code == 401
    new = login(client, "admin@otpco.test", "NewPass-42")
    assert new.status_code == 200
    assert PasswordResetOTP.objects.filter(user=tenant["user"], consumed_at__isnull=True).count() == 0


@pytest.mark.django_db
def test_forgot_password_unknown_slug_does_not_send_mail(client, settings, catalogs):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    response = client.post(
        "/api/v1/auth/password/forgot",
        {"slug": "missing-brand"},
        format="json",
        HTTP_ORIGIN=ORIGIN,
    )
    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_platform_admin_slug_not_applicable(client, settings, catalogs):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    platform_admin("platform-otp@zaylan.test")
    response = client.post(
        "/api/v1/auth/password/forgot",
        {"slug": "nope"},
        format="json",
        HTTP_ORIGIN=ORIGIN,
    )
    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_invalid_otp_is_rejected(client, settings, catalogs):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    create_tenant(slug="badotp", owner_email="owner@badotp.test")
    client.post(
        "/api/v1/auth/password/forgot",
        {"slug": "badotp"},
        format="json",
        HTTP_ORIGIN=ORIGIN,
    )
    response = client.post(
        "/api/v1/auth/password/reset",
        {
            "slug": "badotp",
            "otp": "000000",
            "new_password": "NewPass-42",
        },
        format="json",
        HTTP_ORIGIN=ORIGIN,
    )
    assert response.status_code == 400
