from datetime import date
from decimal import Decimal

import pytest
from apps.catalog.services import create_item, create_recipe
from apps.inventory.models import LocationKind, StockBalance, TransferStatus
from apps.inventory.services import (
    adjust_stock,
    approve_transfer,
    complete_production,
    create_production,
    create_transfer,
    dispatch_transfer,
    receive_transfer,
)
from apps.sales.services import record_sale, reverse_sale
from apps.sales.models import SaleStatus
from tests.factories import (
    PASSWORD,
    add_branch,
    api_client,
    create_tenant,
    accept_owner,
    tenant_ctx,
)


def _item(ctx, sku, name, kind, unit="G"):
    return create_item(
        ctx, {"sku": sku, "name": name, "kind": kind, "base_unit": unit}
    )


def _stock(location_kind, item, branch=None):
    qs = StockBalance.objects.filter(item=item, location__kind=location_kind)
    if branch is not None:
        qs = qs.filter(location__branch=branch)
    return qs.get().quantity


@pytest.mark.django_db
def test_production_transfer_sale_and_refund(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    branch = add_branch(ctx, "BH", "Harbour")
    flour = _item(ctx, "FLOUR", "Flour", "RAW")
    base = _item(ctx, "BASE", "Kunafa base", "SEMI", "EACH")
    pistachio = _item(ctx, "PIST", "Pistachios", "RAW")
    kunafa = _item(ctx, "KUNAFA", "Kunafa", "FINISHED", "EACH")
    today = date.today()
    base_recipe = create_recipe(
        ctx,
        {
            "output_item_id": base.pk,
            "effective_from": today,
            "yield_quantity": 1,
            "lines": [
                {"ingredient_id": flour.pk, "quantity": 20, "unit": "G", "consume_at": "PRODUCTION"}
            ],
        },
    )
    create_recipe(
        ctx,
        {
            "output_item_id": kunafa.pk,
            "effective_from": today,
            "yield_quantity": 1,
            "lines": [
                {"ingredient_id": base.pk, "quantity": 1, "unit": "EACH", "consume_at": "SALE"},
                {"ingredient_id": pistachio.pk, "quantity": 30, "unit": "G", "consume_at": "SALE"},
            ],
        },
    )
    kitchen = branch.organization.inventory_locations.get(kind=LocationKind.CENTRAL_KITCHEN)
    adjust_stock(
        ctx,
        {
            "location_id": kitchen.pk,
            "item_id": flour.pk,
            "quantity": 5000,
            "unit": "G",
            "direction": "in",
            "reason": "ADJUSTMENT",
            "note": "Opening flour",
        },
    )
    adjust_stock(
        ctx,
        {
            "location_id": kitchen.pk,
            "item_id": pistachio.pk,
            "quantity": 5,
            "unit": "KG",
            "direction": "in",
            "reason": "ADJUSTMENT",
            "note": "Opening pistachios",
        },
    )

    order = create_production(ctx, {"recipe_id": base_recipe.pk, "planned_quantity": 100})
    complete_production(ctx, order, {"actual_quantity": 100, "waste_quantity": 0})
    assert _stock(LocationKind.CENTRAL_KITCHEN, flour) == Decimal("3000.000")
    assert _stock(LocationKind.CENTRAL_KITCHEN, base) == Decimal("100.000")

    transfer = create_transfer(
        ctx,
        {
            "branch_id": branch.pk,
            "lines": [
                {"item_id": base.pk, "quantity": 100, "unit": "EACH"},
                {"item_id": pistachio.pk, "quantity": 5, "unit": "KG"},
            ],
        },
    )
    transfer = approve_transfer(ctx, transfer)
    transfer = dispatch_transfer(ctx, transfer)
    assert _stock(LocationKind.CENTRAL_KITCHEN, base) == Decimal("0.000")
    assert _stock(LocationKind.IN_TRANSIT, pistachio) == Decimal("5000.000")
    line_ids = {line.item_id: line for line in transfer.lines.all()}
    transfer = receive_transfer(
        ctx,
        transfer,
        {
            "lines": [
                {"line_id": line_ids[base.pk].pk, "received_quantity": 100, "note": ""},
                {
                    "line_id": line_ids[pistachio.pk].pk,
                    "received_quantity": Decimal("4.8"),
                    "note": "0.2 kg short",
                },
            ]
        },
    )
    pistachio_line = transfer.lines.get(item=pistachio)
    assert pistachio_line.dispatched_quantity == Decimal("5.000")
    assert pistachio_line.received_quantity == Decimal("4.800")
    assert transfer.status == TransferStatus.PARTIALLY_RECEIVED
    assert _stock(LocationKind.BRANCH, base, branch) == Decimal("100.000")
    assert _stock(LocationKind.BRANCH, pistachio, branch) == Decimal("4800.000")
    assert _stock(LocationKind.IN_TRANSIT, pistachio) == Decimal("200.000")

    payload = {
        "branch_id": branch.pk,
        "idempotency_key": "sale-kunafa-10",
        "lines": [{"item_id": kunafa.pk, "quantity": 10}],
    }
    sale = record_sale(ctx, payload)
    again = record_sale(ctx, payload)
    assert again.pk == sale.pk
    assert _stock(LocationKind.BRANCH, base, branch) == Decimal("90.000")
    assert _stock(LocationKind.BRANCH, pistachio, branch) == Decimal("4500.000")

    reverse_sale(ctx, sale, status=SaleStatus.REFUNDED)
    assert _stock(LocationKind.BRANCH, base, branch) == Decimal("100.000")
    assert _stock(LocationKind.BRANCH, pistachio, branch) == Decimal("4800.000")


@pytest.mark.django_db
def test_branch_login_cannot_approve_or_open_another_brand(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    branch = add_branch(ctx, "BH2", "Second")
    from apps.branches.services import update_branch

    update_branch(
        ctx,
        branch,
        {"login_username": "harbourdesk", "login_password": PASSWORD},
    )
    branch.refresh_from_db()
    client = api_client(branch.login_user, organization=owner["organization"])
    denied = client.post(
        "/api/v1/expenses/00000000-0000-0000-0000-000000000000/approve/", format="json"
    )
    assert denied.status_code == 403

    other = accept_owner(create_tenant(slug="otherbrand", name="Other"))
    foreign = api_client(branch.login_user, organization=other["organization"])
    assert foreign.get("/api/v1/inventory/balances").status_code == 403
