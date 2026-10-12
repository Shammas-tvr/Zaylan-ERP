from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from apps.expenses.models import Expense, ExpenseEntryType, ExpenseStatus
from apps.expenses.services import generate_recurring_for_period
from tests.factories import (
    PASSWORD,
    accept_owner,
    add_branch,
    api_client,
    bootstrap_catalogs,
    create_member,
    create_tenant,
    platform_admin,
    tenant_ctx,
)


@pytest.fixture(autouse=True)
def _catalogs(db):
    bootstrap_catalogs()


@pytest.fixture
def owner(db):
    tenant = create_tenant(slug="brand-a")
    data = accept_owner(tenant)
    data["branch"] = add_branch(tenant_ctx(data["user"], data["organization"]), "HQ", "HQ")
    return data


@pytest.fixture
def other_owner(db):
    tenant = create_tenant(slug="brand-b", owner_email="owner@brand-b.test")
    data = accept_owner(tenant)
    data["branch"] = add_branch(tenant_ctx(data["user"], data["organization"]), "HQ", "HQ")
    return data


def _category(client):
    response = client.post(
        "/api/v1/expenses/categories/",
        {"code": "RENT", "name": "Rent"},
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data


@pytest.mark.django_db
def test_platform_can_create_brand_and_invite(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    admin = platform_admin()
    client = api_client(admin)
    response = client.post(
        "/api/v1/platform/tenants",
        {
            "name": "Zaylan",
            "slug": "zaylan-brand",
            "industry": "RETAIL",
            "plan_code": "growth",
            "owner_email": "admin@zaylan.test",
            "legal_name": "Zaylan Pvt Ltd",
            "contact_email": "ops@zaylan.test",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["owner_invitation_url"]
    assert response.data["tenant"]["contact_email"] == "ops@zaylan.test"
    assert response.data["invitation_email_sent"] is True
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_variable_expense_submit_approve_pay_and_self_approval_blocked(owner):
    client = api_client(owner["user"], organization=owner["organization"])
    category = _category(client)
    create = client.post(
        "/api/v1/expenses/",
        {
            "branch_id": str(owner["branch"].pk),
            "category_id": category["id"],
            "amount": "1500.00",
            "expense_date": "2026-10-01",
            "payment_method": "CASH",
            "description": "Water bill",
        },
        format="json",
    )
    assert create.status_code == 201, create.data
    expense_id = create.data["id"]
    submit = client.post(f"/api/v1/expenses/{expense_id}/submit/")
    assert submit.status_code == 200
    assert submit.data["status"] == ExpenseStatus.PENDING_APPROVAL

    # Self-approval blocked
    approve_self = client.post(f"/api/v1/expenses/{expense_id}/approve/")
    assert approve_self.status_code == 403

    # Second admin can approve
    other = create_member(
        owner["organization"],
        email="approver@brand-a.test",
        role_key="accountant",
        scope="TENANT",
    )
    approver = api_client(other["user"], organization=owner["organization"])
    approve = approver.post(f"/api/v1/expenses/{expense_id}/approve/")
    assert approve.status_code == 200, approve.data
    assert approve.data["status"] == ExpenseStatus.APPROVED

    paid = approver.post(
        f"/api/v1/expenses/{expense_id}/mark-paid/",
        {"payment_reference": "UTR-1"},
        format="json",
    )
    assert paid.status_code == 200
    assert paid.data["status"] == ExpenseStatus.PAID
    assert paid.data["payment_reference"] == "UTR-1"


@pytest.mark.django_db
def test_cross_tenant_expense_is_404(owner, other_owner):
    client = api_client(owner["user"], organization=owner["organization"])
    category = _category(client)
    create = client.post(
        "/api/v1/expenses/",
        {
            "branch_id": str(owner["branch"].pk),
            "category_id": category["id"],
            "amount": "10.00",
            "expense_date": "2026-10-01",
            "payment_method": "OTHER",
            "description": "x",
        },
        format="json",
    )
    foreign = api_client(other_owner["user"], organization=other_owner["organization"])
    response = foreign.get(f"/api/v1/expenses/{create.data['id']}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_branch_user_cannot_approve(owner):
    client = api_client(owner["user"], organization=owner["organization"])
    category = _category(client)
    create = client.post(
        "/api/v1/expenses/",
        {
            "branch_id": str(owner["branch"].pk),
            "category_id": category["id"],
            "amount": "40.00",
            "expense_date": "2026-10-02",
            "payment_method": "OTHER",
            "description": "electricity",
        },
        format="json",
    )
    client.post(f"/api/v1/expenses/{create.data['id']}/submit/")
    cashier = create_member(
        owner["organization"],
        email="cashier@brand-a.test",
        role_key="cashier",
        branches=[owner["branch"]],
    )
    branch_client = api_client(cashier["user"], organization=owner["organization"])
    response = branch_client.post(f"/api/v1/expenses/{create.data['id']}/approve/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_recurring_generation_is_idempotent(owner):
    client = api_client(owner["user"], organization=owner["organization"])
    category = _category(client)
    recurring = client.post(
        "/api/v1/expenses/recurring/",
        {
            "branch_id": str(owner["branch"].pk),
            "category_id": category["id"],
            "expected_amount": "25000.00",
            "start_date": "2026-01-01",
            "due_day": 1,
            "description": "Shop rent",
        },
        format="json",
    )
    assert recurring.status_code == 201, recurring.data
    as_of = date(2026, 10, 15)
    first = generate_recurring_for_period(as_of=as_of)
    second = generate_recurring_for_period(as_of=as_of)
    assert first["created"] == 1
    assert second["created"] == 0
    expense = Expense.objects.get(
        organization=owner["organization"],
        billing_period="2026-10",
        entry_type=ExpenseEntryType.RECURRING,
    )
    assert expense.status == ExpenseStatus.PENDING_APPROVAL
    assert expense.amount == Decimal("25000.00")


@pytest.mark.django_db
def test_in_app_notification_on_submit(owner, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    mail.outbox.clear()
    client = api_client(owner["user"], organization=owner["organization"])
    category = _category(client)
    create = client.post(
        "/api/v1/expenses/",
        {
            "branch_id": str(owner["branch"].pk),
            "category_id": category["id"],
            "amount": "99.00",
            "expense_date": str(timezone.localdate()),
            "payment_method": "UPI",
            "description": "misc",
        },
        format="json",
    )
    # Submit as cashier so owner can receive notification without self-submit noise
    cashier = create_member(
        owner["organization"],
        email="c2@brand-a.test",
        role_key="cashier",
        branches=[owner["branch"]],
    )
    # Transfer ownership of draft isn't supported; create as cashier instead
    branch_client = api_client(cashier["user"], organization=owner["organization"])
    create2 = branch_client.post(
        "/api/v1/expenses/",
        {
            "branch_id": str(owner["branch"].pk),
            "category_id": category["id"],
            "amount": "88.00",
            "expense_date": str(timezone.localdate()),
            "payment_method": "UPI",
            "description": "misc2",
        },
        format="json",
    )
    assert create2.status_code == 201, create2.data
    submit = branch_client.post(f"/api/v1/expenses/{create2.data['id']}/submit/")
    assert submit.status_code == 200
    notes = client.get("/api/v1/notifications/")
    assert notes.status_code == 200
    assert notes.data["count"] >= 1 or len(notes.data.get("results", notes.data)) >= 1
    assert len(mail.outbox) >= 1
