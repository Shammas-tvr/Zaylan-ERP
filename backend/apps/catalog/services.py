from datetime import date

from django.db import IntegrityError, transaction
from django.db.models.functions import Upper
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError

from .models import Item, Product, Recipe, RecipeLine, StockUnit
from .units import quantity_in_base

BASE_FOR_STOCK = {
    "G": "G",
    "KG": "G",
    "ML": "ML",
    "L": "ML",
    "EACH": "EACH",
    "BOX": "EACH",
}


def _decimal(value, default="0"):
    from decimal import Decimal

    if value is None or value == "":
        return Decimal(default)
    return Decimal(value)


def _apply_item_units(item: Item, data: dict) -> None:
    stock_unit = (data.get("stock_unit") or data.get("base_unit") or item.stock_unit or item.base_unit).upper()
    if stock_unit not in BASE_FOR_STOCK:
        raise ValidationError({"stock_unit": ["Unknown unit."]})
    item.stock_unit = stock_unit
    item.base_unit = BASE_FOR_STOCK[stock_unit]
    purchase_unit = (data.get("purchase_unit") or stock_unit).upper()
    if purchase_unit not in BASE_FOR_STOCK:
        raise ValidationError({"purchase_unit": ["Unknown unit."]})
    item.purchase_unit = purchase_unit
    factor = _decimal(data.get("purchase_factor"), "1")
    if factor <= 0:
        raise ValidationError({"purchase_factor": ["Conversion must be greater than zero."]})
    item.purchase_factor = factor


def _next_code(organization, model, prefix: str) -> str:
    from apps.tenancy.models import Organization

    Organization.objects.select_for_update().get(pk=organization.pk)
    numbers = []
    skus = (
        model.objects.filter(organization=organization)
        .annotate(sku_upper=Upper("sku"))
        .filter(sku_upper__startswith=prefix)
        .values_list("sku_upper", flat=True)
    )
    for sku in skus:
        tail = sku[len(prefix) :]
        if tail.isdigit():
            numbers.append(int(tail))
    return f"{prefix}{(max(numbers) if numbers else 0) + 1:04d}"


def _item(ctx, item_id) -> Item:
    item = Item.objects.filter(organization=ctx.organization, pk=item_id).first()
    if item is None:
        raise ValidationError({"item_id": ["Unknown item."]})
    return item


@transaction.atomic
def create_item(ctx, data: dict, *, request=None) -> Item:
    sku = (data.get("sku") or "").strip().upper() or _next_code(ctx.organization, Item, "ITM-")
    item = Item(
        organization=ctx.organization,
        sku=sku,
        name=data["name"].strip(),
        kind=data["kind"],
        category=(data.get("category") or "").strip(),
        supplier_name=(data.get("supplier_name") or "").strip(),
        costing_method=data.get("costing_method") or "MOVING_AVERAGE",
        standard_cost=_decimal(data.get("standard_cost")),
        minimum_stock=_decimal(data.get("minimum_stock")),
        tracks_batch=bool(data.get("tracks_batch")),
        tracks_expiry=bool(data.get("tracks_expiry")),
        expiry_date=data.get("expiry_date") if data.get("tracks_expiry") else None,
        tracks_stock=data.get("tracks_stock", True),
        is_active=data.get("is_active", True),
    )
    _apply_item_units(item, data)
    _assign_storage(ctx, item, data)
    try:
        item.save()
    except IntegrityError as exc:
        raise ConflictError("An item with this SKU already exists.") from exc
    record_event(
        action="catalog.item_created",
        actor=ctx.user,
        organization=ctx.organization,
        target=item,
        metadata={"sku": item.sku, "name": item.name},
        request=request,
    )
    return item


@transaction.atomic
def update_item(ctx, item: Item, data: dict, *, request=None) -> Item:
    item = Item.objects.select_for_update().get(pk=item.pk, organization=ctx.organization)
    changed = {}
    for field in (
        "name",
        "kind",
        "category",
        "supplier_name",
        "costing_method",
        "is_active",
        "tracks_batch",
        "tracks_expiry",
        "tracks_stock",
    ):
        if field in data and getattr(item, field) != data[field]:
            value = data[field].strip() if isinstance(data[field], str) else data[field]
            changed[field] = [getattr(item, field), value]
            setattr(item, field, value)
    for field in ("standard_cost", "minimum_stock"):
        if field in data:
            value = _decimal(data[field])
            if getattr(item, field) != value:
                changed[field] = [str(getattr(item, field)), str(value)]
                setattr(item, field, value)
    if "tracks_expiry" in data or "expiry_date" in data:
        tracks = bool(data["tracks_expiry"]) if "tracks_expiry" in data else item.tracks_expiry
        expiry = data.get("expiry_date") if "expiry_date" in data else item.expiry_date
        if not tracks:
            expiry = None
        if item.expiry_date != expiry:
            changed["expiry_date"] = [
                item.expiry_date.isoformat() if item.expiry_date else None,
                expiry.isoformat() if expiry else None,
            ]
            item.expiry_date = expiry
    if "stock_unit" in data or "purchase_unit" in data or "purchase_factor" in data or "base_unit" in data:
        _apply_item_units(item, {**data, "stock_unit": data.get("stock_unit") or item.stock_unit})
    if "storage_location_id" in data:
        _assign_storage(ctx, item, data)
    if "sku" in data:
        sku = data["sku"].strip().upper()
        if sku != item.sku:
            changed["sku"] = [item.sku, sku]
            item.sku = sku
    unit_fields = {"stock_unit", "purchase_unit", "purchase_factor", "base_unit", "storage_location_id"}
    if changed or unit_fields.intersection(data):
        try:
            item.save()
        except IntegrityError as exc:
            raise ConflictError("An item with this SKU already exists.") from exc
        record_event(
            action="catalog.item_updated",
            actor=ctx.user,
            organization=ctx.organization,
            target=item,
            metadata=changed,
            request=request,
        )
    return item


def _assign_storage(ctx, item: Item, data: dict) -> None:
    location_id = data.get("storage_location_id")
    if not location_id:
        if "storage_location_id" in data:
            item.storage_location = None
        return
    from apps.inventory.models import InventoryLocation

    location = InventoryLocation.objects.filter(
        organization=ctx.organization, pk=location_id
    ).first()
    if location is None:
        raise ValidationError({"storage_location_id": ["Unknown location."]})
    item.storage_location = location


def _branches(ctx, ids):
    from apps.branches.models import Branch

    wanted = list(dict.fromkeys(ids or []))
    rows = list(Branch.objects.filter(organization=ctx.organization, pk__in=wanted))
    if len(rows) != len(wanted):
        raise ValidationError({"branch_ids": ["Choose branches in this brand."]})
    return rows


@transaction.atomic
def create_product(ctx, data: dict, *, request=None) -> Product:
    product = Product(
        organization=ctx.organization,
        sku=(data.get("sku") or "").strip().upper() or _next_code(ctx.organization, Product, "PRD-"),
        name=data["name"].strip(),
        category=(data.get("category") or "").strip(),
        selling_price=_decimal(data.get("selling_price")),
        sale_unit=(data.get("sale_unit") or StockUnit.EACH).upper(),
        kind=data.get("kind") or "FINISHED",
        is_active=data.get("is_active", True),
    )
    if data.get("inventory_item_id"):
        product.inventory_item = _item(ctx, data["inventory_item_id"])
    try:
        product.save()
    except IntegrityError as exc:
        raise ConflictError("A product with this SKU already exists.") from exc
    if "branch_ids" in data:
        product.branches.set(_branches(ctx, data["branch_ids"]))
    record_event(
        action="catalog.product_created",
        actor=ctx.user,
        organization=ctx.organization,
        target=product,
        metadata={"sku": product.sku, "name": product.name},
        request=request,
    )
    return product


@transaction.atomic
def update_product(ctx, product: Product, data: dict, *, request=None) -> Product:
    product = Product.objects.select_for_update().get(pk=product.pk, organization=ctx.organization)
    if "name" in data:
        product.name = data["name"].strip()
    if "category" in data:
        product.category = data["category"].strip()
    if "selling_price" in data:
        product.selling_price = _decimal(data["selling_price"])
    if "sale_unit" in data:
        product.sale_unit = data["sale_unit"].upper()
    if "kind" in data:
        product.kind = data["kind"]
    if "is_active" in data:
        product.is_active = data["is_active"]
    if "inventory_item_id" in data:
        product.inventory_item = _item(ctx, data["inventory_item_id"]) if data["inventory_item_id"] else None
    try:
        product.save()
    except IntegrityError as exc:
        raise ConflictError("A product with this SKU already exists.") from exc
    if "branch_ids" in data:
        product.branches.set(_branches(ctx, data["branch_ids"]))
    record_event(
        action="catalog.product_updated",
        actor=ctx.user,
        organization=ctx.organization,
        target=product,
        metadata={"sku": product.sku},
        request=request,
    )
    return product


def effective_recipe(organization, item: Item, on: date | None = None) -> Recipe:
    on = on or timezone.localdate()
    recipe = (
        Recipe.objects.filter(
            organization=organization,
            output_item=item,
            is_active=True,
            effective_from__lte=on,
        )
        .order_by("-effective_from", "-version")
        .first()
    )
    if recipe is None:
        raise BusinessRuleViolation(f"{item.name} has no recipe for {on.isoformat()}.")
    return recipe


@transaction.atomic
def create_recipe(ctx, data: dict, *, request=None) -> Recipe:
    product = None
    if data.get("product_id"):
        product = Product.objects.filter(organization=ctx.organization, pk=data["product_id"]).first()
        if product is None:
            raise ValidationError({"product_id": ["Unknown product."]})
        if product.inventory_item_id is None:
            raise ValidationError(
                {"product_id": ["Link this product to an inventory item before adding a recipe."]}
            )
        output = product.inventory_item
    else:
        output = _item(ctx, data["output_item_id"])
    if data["yield_quantity"] <= 0:
        raise ValidationError({"yield_quantity": ["Yield must be greater than zero."]})
    waste = _decimal(data.get("expected_waste_percent"))
    if waste < 0 or waste > 100:
        raise ValidationError({"expected_waste_percent": ["Wastage must be between 0 and 100."]})
    lines = data["lines"]
    if not lines:
        raise ValidationError({"lines": ["A recipe needs at least one ingredient."]})
    version = (
        Recipe.objects.filter(organization=ctx.organization, output_item=output).count() + 1
    )
    recipe = Recipe.objects.create(
        organization=ctx.organization,
        output_item=output,
        version=version,
        effective_from=data["effective_from"],
        yield_quantity=data["yield_quantity"],
        expected_waste_percent=waste,
        product=product,
    )
    created = []
    for line in lines:
        ingredient = _item(ctx, line["ingredient_id"])
        if ingredient.pk == output.pk and line["consume_at"] == "PRODUCTION":
            raise ValidationError({"lines": ["A production line cannot consume its own output."]})
        quantity_in_base(line["quantity"], line["unit"], ingredient)
        created.append(
            RecipeLine(
                recipe=recipe,
                ingredient=ingredient,
                quantity=line["quantity"],
                unit=line["unit"].upper(),
                consume_at=line["consume_at"],
            )
        )
    RecipeLine.objects.bulk_create(created)
    record_event(
        action="catalog.recipe_created",
        actor=ctx.user,
        organization=ctx.organization,
        target=recipe,
        metadata={"item": output.sku, "version": version},
        request=request,
    )
    return recipe
