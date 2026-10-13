from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, ConflictError

from .models import Item, Recipe, RecipeLine
from .units import to_base


def _item(ctx, item_id) -> Item:
    item = Item.objects.filter(organization=ctx.organization, pk=item_id).first()
    if item is None:
        raise ValidationError({"item_id": ["Unknown item."]})
    return item


@transaction.atomic
def create_item(ctx, data: dict, *, request=None) -> Item:
    item = Item(
        organization=ctx.organization,
        sku=data["sku"].strip().upper(),
        name=data["name"].strip(),
        kind=data["kind"],
        base_unit=data["base_unit"],
    )
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
    for field in ("name", "kind", "base_unit", "is_active"):
        if field in data and getattr(item, field) != data[field]:
            changed[field] = [getattr(item, field), data[field]]
            setattr(item, field, data[field])
    if "sku" in data:
        sku = data["sku"].strip().upper()
        if sku != item.sku:
            changed["sku"] = [item.sku, sku]
            item.sku = sku
    if changed:
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
    output = _item(ctx, data["output_item_id"])
    if data["yield_quantity"] <= 0:
        raise ValidationError({"yield_quantity": ["Yield must be greater than zero."]})
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
    )
    created = []
    for line in lines:
        ingredient = _item(ctx, line["ingredient_id"])
        if ingredient.pk == output.pk and line["consume_at"] == "PRODUCTION":
            raise ValidationError({"lines": ["A production line cannot consume its own output."]})
        to_base(line["quantity"], line["unit"], ingredient.base_unit)
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
