from decimal import Decimal

import pytest
from apps.catalog.services import create_item, update_item
from apps.core.exceptions import ConflictError
from apps.inventory.models import StockBalance
from apps.inventory.services import ensure_branch_location
from tests.factories import add_branch, api_client, bootstrap_catalogs, create_tenant, tenant_ctx


@pytest.mark.django_db
def test_name_codes_are_prefix_sequences_and_do_not_change_stock(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    first = create_item(ctx, {"name": "Pistachio Kunafa", "kind": "RAW", "stock_unit": "KG"})
    second = create_item(ctx, {"name": "Pistachio Cake", "kind": "RAW", "stock_unit": "KG"})
    baklava = create_item(ctx, {"name": "Baklava", "kind": "FINISHED", "stock_unit": "EACH"})
    milk = create_item(ctx, {"name": "Milk", "kind": "RAW", "stock_unit": "L"})
    tea = create_item(ctx, {"name": "Tea", "kind": "RAW", "stock_unit": "G"})
    cup = create_item(ctx, {"name": "Paper Cup", "kind": "PACKAGING", "stock_unit": "PACKET"})

    assert first.sku == "PIST-01"
    assert second.sku == "PIST-02"
    assert baklava.sku == "BAKL-01"
    assert milk.sku == "MILK-01"
    assert tea.sku == "TEA-01"
    assert cup.sku == "PAPE-01"
    assert StockBalance.objects.filter(item=first).count() == 0

    update_item(ctx, first, {"name": "Pistachio Special"})
    first.refresh_from_db()
    assert first.name == "Pistachio Special"
    assert first.sku == "PIST-01"


@pytest.mark.django_db
def test_code_sequence_continues_past_99_for_the_same_prefix(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    create_item(ctx, {"sku": "PIST-99", "name": "Older pistachio", "kind": "RAW", "stock_unit": "KG"})
    nxt = create_item(ctx, {"name": "Pistachio next", "kind": "RAW", "stock_unit": "KG"})
    assert nxt.sku == "PIST-100"


@pytest.mark.django_db
def test_branch_minimum_is_separate_and_listing_uses_that_location(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    tenant = owner
    harbour = add_branch(ctx, "HB", "Harbour")
    creek = add_branch(ctx, "CR", "Creek")
    harbour_location = ensure_branch_location(harbour)
    creek_location = ensure_branch_location(creek)
    item = create_item(
        ctx,
        {
            "name": "Butter",
            "kind": "RAW",
            "stock_unit": "KG",
            "standard_cost": "80",
            "costing_method": "FIFO",
            "stock_policies": [
                {"location_id": harbour_location.pk, "minimum_quantity": "2"},
                {"location_id": creek_location.pk, "minimum_quantity": "5"},
            ],
        },
    )
    assert item.minimum_stock == 0
    assert StockBalance.objects.filter(item=item).count() == 0
    policies = {row.location_id: row.minimum_quantity for row in item.location_policies.all()}
    assert policies[harbour_location.pk] == Decimal("2")
    assert policies[creek_location.pk] == Decimal("5")

    client = api_client(tenant["user"], organization=tenant["organization"])
    harbour_rows = client.get(f"/api/v1/catalog/items/?location={harbour_location.pk}").data["results"]
    creek_rows = client.get(f"/api/v1/catalog/items/?location={creek_location.pk}").data["results"]
    harbour_row = next(row for row in harbour_rows if row["id"] == str(item.pk))
    creek_row = next(row for row in creek_rows if row["id"] == str(item.pk))
    assert harbour_row["branch_quantity"] == "0.000"
    assert harbour_row["branch_minimum"] == "2.000"
    assert harbour_row["stock_status"] == "out"
    assert creek_row["branch_minimum"] == "5.000"
    assert creek_row["stock_status"] == "out"
    assert harbour_row["sku"] == "BUTT-01"


@pytest.mark.django_db
def test_duplicate_explicit_code_is_rejected(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    create_item(ctx, {"sku": "MILK-01", "name": "Milk", "kind": "RAW", "stock_unit": "L"})
    with pytest.raises(ConflictError):
        create_item(ctx, {"sku": "milk-01", "name": "Another milk", "kind": "RAW", "stock_unit": "L"})


@pytest.mark.django_db(transaction=True)
def test_concurrent_creates_do_not_share_a_code():
    import threading

    bootstrap_catalogs()
    tenant = create_tenant(slug="concurrent-codes")
    ctx = tenant_ctx(tenant["user"], tenant["organization"])
    errors = []

    def make(index):
        try:
            create_item(ctx, {"name": f"Pistachio batch {index}", "kind": "RAW", "stock_unit": "KG"})
        except Exception as exc:  # noqa: BLE001 - collect thread failures
            errors.append(exc)

    threads = [threading.Thread(target=make, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    from apps.catalog.models import Item

    skus = set(Item.objects.filter(organization=tenant["organization"]).values_list("sku", flat=True))
    assert skus == {f"PIST-{index:02d}" for index in range(1, 7)}
