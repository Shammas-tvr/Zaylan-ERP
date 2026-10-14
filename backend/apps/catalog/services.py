import re
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models.functions import Upper
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError

from apps.core.storage import owned_image_key

from .models import Item, ItemLocationPolicy, Product, Recipe, RecipeLine, RecipeStatus, StockUnit, Supplier
from .units import quantity_in_base, stock_factor

BASE_FOR_STOCK = {
    "G": "G",
    "KG": "G",
    "ML": "ML",
    "L": "ML",
    "EACH": "EACH",
    "BOX": "EACH",
    "PACKET": "EACH",
    "BOTTLE": "EACH",
    "TRAY": "EACH",
}


def line_cost(line) -> "Decimal":
    from decimal import Decimal

    base = quantity_in_base(line.quantity, line.unit, line.ingredient)
    factor = stock_factor(line.ingredient.stock_unit or line.ingredient.base_unit)
    per_base = Decimal(line.ingredient.standard_cost) / factor
    return base * per_base


def ingredient_cost_per_unit(recipe: Recipe):
    from decimal import Decimal

    total = sum((line_cost(line) for line in recipe.lines.all()), Decimal("0"))
    yield_quantity = Decimal(recipe.yield_quantity or 1)
    if yield_quantity <= 0:
        yield_quantity = Decimal("1")
    return (total / yield_quantity).quantize(Decimal("0.01"))


def product_estimate(product: Product) -> dict:
    from decimal import Decimal

    active = [row for row in product.recipes.all() if row.is_active]
    active.sort(key=lambda row: (row.effective_from, row.version), reverse=True)
    latest = active[0] if active else None
    confirmed = [row for row in active if row.status == RecipeStatus.CONFIRMED]
    recipe = confirmed[0] if confirmed else None
    ingredient = ingredient_cost_per_unit(recipe) if recipe is not None else Decimal("0.00")
    labour = Decimal(product.labour_cost or 0)
    overhead = Decimal(product.overhead_cost or 0)
    total = (ingredient + labour + overhead).quantize(Decimal("0.01"))
    price = Decimal(product.selling_price or 0)
    if price > 0:
        profit = (price - total).quantize(Decimal("0.01"))
        margin = (profit / price * Decimal("100")).quantize(Decimal("0.01"))
    else:
        profit = None
        margin = None
    return {
        "recipe_id": str(recipe.pk) if recipe else None,
        "recipe_status": latest.status if latest else "none",
        "recipe_version": latest.version if latest else None,
        "ingredient_cost": str(ingredient),
        "labour_cost": str(labour.quantize(Decimal("0.01"))),
        "overhead_cost": str(overhead.quantize(Decimal("0.01"))),
        "estimated_cost": str(total),
        "gross_profit": None if profit is None else str(profit),
        "gross_margin": None if margin is None else str(margin),
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


def _clean_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", (value or "").strip().upper())


def _name_code(organization, model, name: str, fallback: str) -> str:
    from apps.tenancy.models import Organization

    Organization.objects.select_for_update().get(pk=organization.pk)
    letters = re.sub(r"[^A-Z0-9]", "", (name or "").upper())
    base = letters[:4] or fallback.upper()
    prefix = f"{base}-"
    numbers = []
    skus = (
        model.objects.filter(organization=organization)
        .annotate(sku_upper=Upper("sku"))
        .filter(sku_upper__startswith=prefix.upper())
        .values_list("sku_upper", flat=True)
    )
    for sku in skus:
        tail = sku[len(prefix) :]
        if tail.isdigit():
            numbers.append(int(tail))
    # Next number for this prefix, not a count of all items. Width grows past 99 (PIST-100).
    return f"{prefix}{(max(numbers) if numbers else 0) + 1:02d}"


def _item(ctx, item_id) -> Item:
    item = Item.objects.filter(organization=ctx.organization, pk=item_id).first()
    if item is None:
        raise ValidationError({"item_id": ["Unknown item."]})
    return item


@transaction.atomic
def create_item(ctx, data: dict, *, request=None) -> Item:
    provided = _clean_code(data.get("sku") or "")
    name = data["name"].strip()
    item = Item(
        organization=ctx.organization,
        sku=provided or "PENDING",
        name=name,
        kind=data["kind"],
        category=(data.get("category") or "").strip(),
        supplier_name=(data.get("supplier_name") or "").strip(),
        costing_method=data.get("costing_method") or "MOVING_AVERAGE",
        standard_cost=_decimal(data.get("standard_cost")),
        minimum_stock=_decimal(data.get("minimum_stock")) if "minimum_stock" in data else 0,
        tracks_batch=bool(data.get("tracks_batch")),
        tracks_expiry=bool(data.get("tracks_expiry")),
        expiry_date=data.get("expiry_date") if data.get("tracks_expiry") else None,
        tracks_stock=data.get("tracks_stock", True),
        is_active=data.get("is_active", True),
    )
    if "image_key" in data:
        item.image_key = owned_image_key(ctx.organization.pk, data.get("image_key") or "")
    _apply_item_units(item, data)
    _assign_storage(ctx, item, data)
    _assign_suppliers(ctx, item, data, save=False)
    saved = False
    for _attempt in range(5):
        item.sku = provided or _name_code(ctx.organization, Item, name, "ITEM")
        try:
            with transaction.atomic():
                item.save()
            saved = True
            break
        except IntegrityError as exc:
            item.pk = None
            if provided:
                raise ConflictError("An item with this code already exists.") from exc
    if not saved:
        raise ConflictError("An item with this code already exists.")
    _assign_suppliers(ctx, item, data, save=True)
    _assign_policies(ctx, item, data)
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
        "image_key",
    ):
        if field in data and getattr(item, field) != data[field]:
            value = data[field].strip() if isinstance(data[field], str) else data[field]
            if field == "image_key":
                value = owned_image_key(ctx.organization.pk, value)
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
    # An existing code stays put when the name changes. Codes are not rewritten on edit.
    supplier_fields = {"supplier_ids", "default_supplier_id"}
    if supplier_fields.intersection(data):
        _assign_suppliers(ctx, item, data, save=False)
    if "stock_policies" in data:
        _assign_policies(ctx, item, data)
    unit_fields = {"stock_unit", "purchase_unit", "purchase_factor", "base_unit", "storage_location_id"}
    if changed or unit_fields.intersection(data) or supplier_fields.intersection(data) or "stock_policies" in data:
        try:
            item.save()
        except IntegrityError as exc:
            raise ConflictError("An item with this code already exists.") from exc
        record_event(
            action="catalog.item_updated",
            actor=ctx.user,
            organization=ctx.organization,
            target=item,
            metadata=changed,
            request=request,
        )
    return item


def _suppliers_for(ctx, ids) -> list[Supplier]:
    wanted = list(dict.fromkeys(ids or []))
    rows = list(Supplier.objects.filter(organization=ctx.organization, pk__in=wanted, is_active=True))
    if len(rows) != len(wanted):
        raise ValidationError({"supplier_ids": ["Choose suppliers for this brand."]})
    return rows


def _assign_suppliers(ctx, item: Item, data: dict, *, save: bool) -> None:
    if "supplier_ids" not in data and "default_supplier_id" not in data:
        return
    ids = [str(value) for value in (data.get("supplier_ids") or [])]
    default_id = data.get("default_supplier_id")
    if default_id:
        default_key = str(default_id)
        if default_key not in ids:
            ids.append(default_key)
    else:
        default_key = ""
    rows = _suppliers_for(ctx, ids)
    by_id = {str(row.pk): row for row in rows}
    if item.pk:
        item.suppliers.set(rows)
    item.default_supplier = by_id.get(default_key) if default_key else None
    if item.default_supplier_id and not item.supplier_name:
        item.supplier_name = item.default_supplier.name
    if save and item.pk:
        item.save(update_fields=["default_supplier", "supplier_name", "updated_at"])


def _visible_locations(ctx):
    from apps.inventory.models import InventoryLocation
    from apps.inventory.services import visible_locations

    if ctx.has_permission("catalog.manage") or ctx.has_permission("inventory.view"):
        return InventoryLocation.objects.filter(organization=ctx.organization)
    return visible_locations(ctx)


def _assign_policies(ctx, item: Item, data: dict) -> None:
    if "stock_policies" not in data or not item.pk:
        return
    from apps.inventory.models import LocationKind

    allowed = {location.pk: location for location in _visible_locations(ctx)}
    submitted = []
    for row in data.get("stock_policies") or []:
        location = allowed.get(row["location_id"])
        if location is None or location.kind == LocationKind.IN_TRANSIT:
            raise ValidationError({"stock_policies": ["Choose a branch or storage location you can use."]})
        minimum = _decimal(row.get("minimum_quantity"))
        if minimum < 0:
            raise ValidationError({"stock_policies": ["Minimum stock cannot be negative."]})
        submitted.append((location, minimum))
    visible_ids = list(allowed)
    ItemLocationPolicy.objects.filter(item=item, location_id__in=visible_ids).delete()
    ItemLocationPolicy.objects.bulk_create(
        [
            ItemLocationPolicy(item=item, location=location, minimum_quantity=minimum)
            for location, minimum in submitted
        ]
    )


def create_supplier(ctx, name: str) -> Supplier:
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValidationError({"name": ["Enter a supplier name."]})
    existing = (
        Supplier.objects.annotate(name_upper=Upper("name"))
        .filter(organization=ctx.organization, name_upper=cleaned.upper())
        .first()
    )
    if existing:
        return existing
    try:
        return Supplier.objects.create(organization=ctx.organization, name=cleaned)
    except IntegrityError as exc:
        raise ConflictError("A supplier with this name already exists.") from exc


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


def _finished_item(ctx, product: Product) -> Item:
    """A stock item for the finished product. Creating it does not add quantity."""
    kind = product.kind if product.kind in {"SEMI", "FINISHED", "RESALE"} else "FINISHED"
    return create_item(
        ctx,
        {
            "name": product.name,
            "kind": kind,
            "stock_unit": product.sale_unit or "EACH",
            "category": product.category,
            "standard_cost": "0",
        },
    )


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
        sku=_clean_code(data.get("sku") or "") or _name_code(ctx.organization, Product, data["name"], "prod"),
        name=data["name"].strip(),
        category=(data.get("category") or "").strip(),
        description=(data.get("description") or "").strip(),
        image_key=owned_image_key(ctx.organization.pk, data.get("image_key") or ""),
        selling_price=_decimal(data.get("selling_price")),
        labour_cost=_decimal(data.get("labour_cost")),
        overhead_cost=_decimal(data.get("overhead_cost")),
        sale_unit=(data.get("sale_unit") or StockUnit.EACH).upper(),
        kind=data.get("kind") or "FINISHED",
        is_active=data.get("is_active", True),
    )
    if data.get("inventory_item_id"):
        product.inventory_item = _item(ctx, data["inventory_item_id"])
    else:
        product.inventory_item = _finished_item(ctx, product)
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
    if "description" in data:
        product.description = data["description"].strip()
    if "image_key" in data:
        product.image_key = owned_image_key(ctx.organization.pk, data.get("image_key") or "")
    if "selling_price" in data:
        product.selling_price = _decimal(data["selling_price"])
    if "labour_cost" in data:
        product.labour_cost = _decimal(data["labour_cost"])
    if "overhead_cost" in data:
        product.overhead_cost = _decimal(data["overhead_cost"])
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
            status=RecipeStatus.CONFIRMED,
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
            product.inventory_item = _finished_item(ctx, product)
            product.save(update_fields=["inventory_item", "updated_at"])
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
    ingredient_ids = [str(line["ingredient_id"]) for line in lines]
    if len(ingredient_ids) != len(set(ingredient_ids)):
        raise ValidationError({"lines": ["Each ingredient can appear only once."]})
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
        status=data.get("status") or RecipeStatus.CONFIRMED,
    )
    created = []
    for line in lines:
        ingredient = _item(ctx, line["ingredient_id"])
        if ingredient.pk == output.pk:
            raise ValidationError({"lines": ["A product cannot be an ingredient in its own recipe."]})
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
