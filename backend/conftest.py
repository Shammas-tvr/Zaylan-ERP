import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from tests.factories import (
    ORIGIN,
    accept_owner,
    api_client,
    bootstrap_catalogs,
    create_tenant,
    platform_admin,
)

pytest_plugins = []


@pytest.fixture(autouse=True)
def _trusted_origins():
    with override_settings(
        FRONTEND_ORIGINS=[ORIGIN],
        AUTH_TRUSTED_ORIGINS=[ORIGIN],
        CSRF_TRUSTED_ORIGINS=[ORIGIN],
        CORS_ALLOWED_ORIGINS=[ORIGIN],
        AUTH_REFRESH_COOKIE={
            "NAME": "zaylan_refresh",
            "PATH": "/api/v1/auth/",
            "SECURE": False,
            "SAMESITE": "Lax",
            "DOMAIN": None,
        },
    ):
        yield


@pytest.fixture
def catalogs(db):
    bootstrap_catalogs()


@pytest.fixture
def tenant(catalogs):
    return create_tenant(slug="acme")


@pytest.fixture
def other_tenant(catalogs):
    return create_tenant(slug="beta", name="Beta")


@pytest.fixture
def owner(tenant):
    return accept_owner(tenant)


@pytest.fixture
def other_owner(other_tenant):
    return accept_owner(other_tenant, email="owner@beta.test")


@pytest.fixture
def admin(catalogs):
    return platform_admin()


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_client(owner):
    return api_client(owner["user"])


@pytest.fixture
def admin_client(admin):
    return api_client(admin, origin=ORIGIN)
