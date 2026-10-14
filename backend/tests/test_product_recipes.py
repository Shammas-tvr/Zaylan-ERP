from datetime import date
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from apps.catalog.services import create_item, create_product, create_recipe, product_estimate, update_product
from apps.core.exceptions import BusinessRuleViolation
from apps.core.storage import create_image_upload, owned_image_key
from apps.inventory.models import LocationKind, StockBalance, StockMovement
from apps.inventory.services import (
    adjust_stock,
    complete_production,
    create_production,
    ensure_brand_locations,
)
from tests.factories import api_client, tenant_ctx


def _product(ctx, **extra):
    data = {
        "name": "Pistachio Kunafa",
        "category": "Desserts",
        "selling_price": "20",
        "sale_unit": "EACH",
        "kind": "FINISHED",
        "labour_cost": "2",
        "overhead_cost": "1",
    }
    data.update(extra)
    return create_product(ctx, data)


@pytest.mark.django_db
def test_product_code_and_recipe_cost_do_not_change_stock(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    product = _product(ctx)
    cream = create_item(ctx, {"name": "Cream", "kind": "RAW", "stock_unit": "KG", "standard_cost": "10"})
    pistachio = create_item(ctx, {"name": "Pistachio", "kind": "RAW", "stock_unit": "KG", "standard_cost": "40"})

    assert product.sku == "PIST-01"
    assert product.inventory_item.sku == "PIST-01"
    assert StockBalance.objects.filter(item=product.inventory_item).count() == 0
    movements = StockMovement.objects.count()

    recipe = create_recipe(
        ctx,
        {
            "product_id": product.pk,
            "effective_from": date.today(),
            "yield_quantity": 1,
            "expected_waste_percent": 0,
            "lines": [
                {"ingredient_id": cream.pk, "quantity": 80, "unit": "G", "consume_at": "PRODUCTION"},
                {"ingredient_id": pistachio.pk, "quantity": 20, "unit": "G", "consume_at": "PRODUCTION"},
            ],
        },
    )
    assert StockMovement.objects.count() == movements
    assert recipe.product_id == product.pk
    assert recipe.status == "CONFIRMED"

    product.refresh_from_db()
    estimate = product_estimate(product)
    assert estimate["ingredient_cost"] == "1.60"
    assert estimate["estimated_cost"] == "4.60"
    assert estimate["gross_profit"] == "15.40"
    assert estimate["gross_margin"] == "77.00"
    assert estimate["recipe_status"] == "CONFIRMED"

    update_product(ctx, product, {"name": "Pistachio Special"})
    product.refresh_from_db()
    assert product.sku == "PIST-01"


@pytest.mark.django_db
def test_missing_price_and_invalid_recipe_lines(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    prep = _product(ctx, name="Kunafa base", kind="SEMI", selling_price="0", labour_cost="0", overhead_cost="0")
    estimate = product_estimate(prep)
    assert estimate["gross_profit"] is None
    assert estimate["gross_margin"] is None
    assert estimate["recipe_status"] == "none"

    flour = create_item(ctx, {"name": "Flour", "kind": "RAW", "stock_unit": "KG", "standard_cost": "5"})
    with pytest.raises(ValidationError):
        create_recipe(
            ctx,
            {
                "product_id": prep.pk,
                "effective_from": date.today(),
                "yield_quantity": 1,
                "lines": [
                    {"ingredient_id": flour.pk, "quantity": 100, "unit": "G", "consume_at": "PRODUCTION"},
                    {"ingredient_id": flour.pk, "quantity": 50, "unit": "G", "consume_at": "PRODUCTION"},
                ],
            },
        )
    with pytest.raises(ValidationError):
        create_recipe(
            ctx,
            {
                "product_id": prep.pk,
                "effective_from": date.today(),
                "yield_quantity": 1,
                "lines": [
                    {"ingredient_id": prep.inventory_item.pk, "quantity": 1, "unit": "EACH", "consume_at": "PRODUCTION"},
                ],
            },
        )
    assert StockMovement.objects.count() == 0


@pytest.mark.django_db
def test_confirmed_production_snapshots_cost_and_moves_stock_once(owner):
    ctx = tenant_ctx(owner["user"], owner["organization"])
    product = _product(ctx)
    cream = create_item(ctx, {"name": "Cream", "kind": "RAW", "stock_unit": "KG", "standard_cost": "10"})
    pistachio = create_item(ctx, {"name": "Pistachio", "kind": "RAW", "stock_unit": "KG", "standard_cost": "40"})
    recipe = create_recipe(
        ctx,
        {
            "product_id": product.pk,
            "effective_from": date.today(),
            "yield_quantity": 1,
            "lines": [
                {"ingredient_id": cream.pk, "quantity": 80, "unit": "G", "consume_at": "PRODUCTION"},
                {"ingredient_id": pistachio.pk, "quantity": 20, "unit": "G", "consume_at": "PRODUCTION"},
            ],
        },
    )
    draft = create_recipe(
        ctx,
        {
            "product_id": product.pk,
            "effective_from": date.today(),
            "yield_quantity": 1,
            "status": "DRAFT",
            "lines": [
                {"ingredient_id": cream.pk, "quantity": 10, "unit": "G", "consume_at": "PRODUCTION"},
            ],
        },
    )
    with pytest.raises(ValidationError):
        create_production(ctx, {"recipe_id": draft.pk, "planned_quantity": 1})

    kitchen, _ = ensure_brand_locations(owner["organization"])
    assert kitchen.kind == LocationKind.CENTRAL_KITCHEN
    for item in (cream, pistachio):
        adjust_stock(
            ctx,
            {
                "location_id": kitchen.pk,
                "item_id": item.pk,
                "quantity": 1,
                "unit": "KG",
                "direction": "in",
                "reason": "ADJUSTMENT",
            },
        )
    order = create_production(ctx, {"recipe_id": recipe.pk, "planned_quantity": 1})
    complete_production(ctx, order, {"actual_quantity": 1, "waste_quantity": 0})
    order.refresh_from_db()
    assert order.unit_cost == Decimal("4.6000")
    assert order.production_cost == Decimal("4.60")
    assert order.recipe.version == recipe.version

    balances = {
        row.item_id: row.quantity
        for row in StockBalance.objects.filter(location=kitchen, item__in=[cream, pistachio, product.inventory_item])
    }
    assert balances[cream.pk] == Decimal("920.000")
    assert balances[pistachio.pk] == Decimal("980.000")
    assert balances[product.inventory_item.pk] == Decimal("1.000")

    with pytest.raises(BusinessRuleViolation):
        complete_production(ctx, order, {"actual_quantity": 1, "waste_quantity": 0})
    assert StockBalance.objects.get(location=kitchen, item=cream).quantity == Decimal("920.000")


@pytest.mark.django_db
def test_image_keys_stay_in_the_brand_and_uploads_need_r2(owner, other_owner):
    with pytest.raises(ValidationError):
        create_image_upload(
            organization_id=owner["organization"].pk,
            purpose="product",
            content_type="image/png",
            filename="kunafa.png",
        )
    with pytest.raises(ValidationError):
        create_image_upload(
            organization_id=owner["organization"].pk,
            purpose="item",
            content_type="image/gif",
            filename="kunafa.gif",
        )
    with pytest.raises(ValidationError):
        owned_image_key(
            owner["organization"].pk,
            f"org/{other_owner['organization'].pk}/item/photo.png",
        )

    client = api_client(owner["user"], organization=owner["organization"])
    missing = client.post(
        "/api/v1/catalog/products/",
        {"name": "Plain box", "selling_price": "5", "kind": "FINISHED"},
        format="json",
    )
    assert missing.status_code == 400

    created = client.post(
        "/api/v1/catalog/products/",
        {
            "name": "Baklava",
            "category": "Desserts",
            "selling_price": "12",
            "kind": "FINISHED",
            "sale_unit": "EACH",
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.data["sku"] == "BAKL-01"
    assert created.data["costing"]["recipe_status"] == "none"
    assert created.data["image_url"] is None
