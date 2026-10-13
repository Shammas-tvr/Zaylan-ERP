"""Append-only stock ledger. Balances change only inside the same transaction as a movement."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit_logs.services import record_event
from apps.catalog.models import ConsumeAt, Item
from apps.catalog.services import effective_recipe
from apps.catalog.units import quantity_in_base, to_base
from apps.core.exceptions import BusinessRuleViolation
from apps.notifications.models import NotificationType
from apps.notifications.services import (
    brand_admin_users,
    get_or_create_settings,
    notify_users,
)

from .models import (
    InventoryLocation,
    LocationKind,
    MovementReason,
    ProductionOrder,
    ProductionStatus,
    StockBalance,
    StockMovement,
    StockTransfer,
    StockTransferLine,
    TransferStatus,
)


def ensure_brand_locations(organization) -> tuple[InventoryLocation, InventoryLocation]:
    kitchen, _ = InventoryLocation.objects.get_or_create(
        organization=organization,
        kind=LocationKind.CENTRAL_KITCHEN,
        defaults={"name": "Central kitchen"},
    )
    transit, _ = InventoryLocation.objects.get_or_create(
        organization=organization,
        kind=LocationKind.IN_TRANSIT,
        defaults={"name": "In transit"},
    )
    return kitchen, transit


def ensure_branch_location(branch) -> InventoryLocation:
    ensure_brand_locations(branch.organization)
    location, _ = InventoryLocation.objects.get_or_create(
        organization=branch.organization,
        branch=branch,
        defaults={"kind": LocationKind.BRANCH, "name": branch.name},
    )
    if location.name != branch.name:
        location.name = branch.name
        location.save(update_fields=["name", "updated_at"])
    return location


def ensure_org_locations(organization):
    """Kitchen, in-transit, and one location per branch. Safe to call on every inventory read."""
    ensure_brand_locations(organization)
    from apps.branches.models import Branch

    for branch in Branch.objects.filter(organization=organization):
        ensure_branch_location(branch)


def _lock_balance(organization, location, item) -> StockBalance:
    balance = (
        StockBalance.objects.select_for_update()
        .filter(organization=organization, location=location, item=item)
        .first()
    )
    if balance is None:
        try:
            balance = StockBalance.objects.create(
                organization=organization, location=location, item=item, quantity=Decimal("0")
            )
        except IntegrityError:
            balance = StockBalance.objects.get(
                organization=organization, location=location, item=item
            )
        balance = StockBalance.objects.select_for_update().get(pk=balance.pk)
    return balance


def post_movement(
    *,
    ctx,
    location,
    item,
    quantity: Decimal,
    reason: str,
    reference_type: str = "",
    reference_id=None,
    note: str = "",
    idempotency_key: str = "",
) -> StockMovement:
    quantity = Decimal(quantity)
    if quantity == 0:
        raise ValidationError({"quantity": ["A movement cannot be zero."]})
    if idempotency_key:
        existing = StockMovement.objects.filter(
            organization=ctx.organization, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return existing
    balance = _lock_balance(ctx.organization, location, item)
    updated = balance.quantity + quantity
    if updated < 0:
        raise BusinessRuleViolation(
            f"Not enough {item.name} at {location.name}. On hand: {balance.quantity}."
        )
    balance.quantity = updated
    balance.save(update_fields=["quantity", "updated_at"])
    return StockMovement.objects.create(
        organization=ctx.organization,
        location=location,
        item=item,
        quantity=quantity,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
        idempotency_key=idempotency_key,
        actor=ctx.user,
    )


def _scale(recipe, output_quantity: Decimal) -> Decimal:
    if output_quantity <= 0:
        raise ValidationError({"quantity": ["Quantity must be greater than zero."]})
    return Decimal(output_quantity) / Decimal(recipe.yield_quantity)


def _consume_lines(ctx, *, recipe, location, scale: Decimal, consume_at: str, reference_type, reference_id, reason):
    lines = recipe.lines.filter(consume_at=consume_at).select_related("ingredient")
    for line in lines:
        if not line.ingredient.tracks_stock:
            continue
        base_qty = quantity_in_base(line.quantity, line.unit, line.ingredient) * scale
        post_movement(
            ctx=ctx,
            location=location,
            item=line.ingredient,
            quantity=-base_qty,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=f"{reference_type}:{reference_id}:{consume_at}:{line.pk}",
        )


def visible_locations(ctx):
    qs = InventoryLocation.objects.filter(organization=ctx.organization)
    if ctx.has_permission("inventory.view") or ctx.has_permission("inventory.dispatch"):
        return qs
    branch_ids = ctx.branch_ids_with("inventory.view") | ctx.branch_ids_with("inventory.receive")
    return qs.filter(branch_id__in=branch_ids)


@transaction.atomic
def create_production(ctx, data: dict, *, request=None) -> ProductionOrder:
    if not ctx.has_permission("production.manage"):
        raise PermissionDenied()
    kitchen, _ = ensure_brand_locations(ctx.organization)
    from apps.catalog.models import Recipe

    recipe = (
        Recipe.objects.filter(organization=ctx.organization, pk=data["recipe_id"], is_active=True)
        .select_related("output_item")
        .first()
    )
    if recipe is None:
        raise ValidationError({"recipe_id": ["Unknown recipe."]})
    order = ProductionOrder.objects.create(
        organization=ctx.organization,
        location=kitchen,
        recipe=recipe,
        planned_quantity=data["planned_quantity"],
    )
    record_event(
        action="production.created",
        actor=ctx.user,
        organization=ctx.organization,
        target=order,
        metadata={"recipe": str(recipe.pk), "planned": str(order.planned_quantity)},
        request=request,
    )
    return order


@transaction.atomic
def complete_production(ctx, order: ProductionOrder, data: dict, *, request=None) -> ProductionOrder:
    if not ctx.has_permission("production.manage"):
        raise PermissionDenied()
    order = ProductionOrder.objects.select_for_update().select_related("recipe__output_item", "location").get(
        pk=order.pk, organization=ctx.organization
    )
    if order.status != ProductionStatus.DRAFT:
        raise BusinessRuleViolation("This production order is already completed.")
    actual = Decimal(data["actual_quantity"])
    waste = Decimal(data.get("waste_quantity") or 0)
    if waste < 0 or waste > actual:
        raise ValidationError({"waste_quantity": ["Waste cannot exceed the amount produced."]})
    recipe = order.recipe
    scale = _scale(recipe, actual)
    _consume_lines(
        ctx,
        recipe=recipe,
        location=order.location,
        scale=scale,
        consume_at=ConsumeAt.PRODUCTION,
        reference_type="production",
        reference_id=order.pk,
        reason=MovementReason.PRODUCTION_CONSUME,
    )
    if recipe.output_item.tracks_stock:
        output_base = to_base(actual, recipe.output_item.base_unit, recipe.output_item.base_unit)
        post_movement(
            ctx=ctx,
            location=order.location,
            item=recipe.output_item,
            quantity=output_base,
            reason=MovementReason.PRODUCTION_OUTPUT,
            reference_type="production",
            reference_id=order.pk,
            idempotency_key=f"production:{order.pk}:output",
        )
        if waste > 0:
            post_movement(
                ctx=ctx,
                location=order.location,
                item=recipe.output_item,
                quantity=-to_base(waste, recipe.output_item.base_unit, recipe.output_item.base_unit),
                reason=MovementReason.PRODUCTION_WASTE,
                reference_type="production",
                reference_id=order.pk,
                idempotency_key=f"production:{order.pk}:waste",
            )
    order.actual_quantity = actual
    order.waste_quantity = waste
    order.status = ProductionStatus.COMPLETED
    order.completed_at = timezone.now()
    order.save()
    record_event(
        action="production.completed",
        actor=ctx.user,
        organization=ctx.organization,
        target=order,
        metadata={"actual": str(actual), "waste": str(waste)},
        request=request,
    )
    return order


def _next_transfer_number(organization) -> str:
    type(organization).objects.select_for_update().get(pk=organization.pk)
    count = StockTransfer.objects.filter(organization=organization).count() + 1
    return f"TR-{count:04d}"


@transaction.atomic
def create_transfer(ctx, data: dict, *, request=None) -> StockTransfer:
    if not ctx.has_permission("inventory.dispatch"):
        raise PermissionDenied()
    kitchen, _ = ensure_brand_locations(ctx.organization)
    from apps.branches.models import Branch

    branch = Branch.objects.filter(organization=ctx.organization, pk=data["branch_id"]).first()
    if branch is None:
        raise ValidationError({"branch_id": ["Unknown branch."]})
    destination = ensure_branch_location(branch)
    source_id = data.get("source_location_id")
    if source_id:
        source = InventoryLocation.objects.filter(
            organization=ctx.organization, pk=source_id
        ).exclude(kind=LocationKind.IN_TRANSIT).first()
        if source is None:
            raise ValidationError({"source_location_id": ["Unknown source location."]})
    else:
        source = kitchen
    if source.pk == destination.pk:
        raise ValidationError({"source_location_id": ["Source and destination must be different."]})
    lines = data["lines"]
    if not lines:
        raise ValidationError({"lines": ["Add at least one item."]})
    transfer = StockTransfer.objects.create(
        organization=ctx.organization,
        number=_next_transfer_number(ctx.organization),
        source_location=source,
        destination_location=destination,
        status=TransferStatus.DRAFT,
    )
    created = []
    for line in lines:
        item = Item.objects.filter(organization=ctx.organization, pk=line["item_id"]).first()
        if item is None:
            raise ValidationError({"lines": ["Unknown item."]})
        if not item.tracks_stock:
            raise ValidationError({"lines": [f"{item.name} does not track stock."]})
        quantity_in_base(line["quantity"], line["unit"], item)
        created.append(
            StockTransferLine(
                transfer=transfer,
                item=item,
                unit=line["unit"].upper(),
                requested_quantity=line["quantity"],
            )
        )
    StockTransferLine.objects.bulk_create(created)
    record_event(
        action="inventory.transfer_created",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=transfer,
        metadata={"number": transfer.number},
        request=request,
    )
    return transfer


@transaction.atomic
def approve_transfer(ctx, transfer: StockTransfer, *, request=None) -> StockTransfer:
    if not ctx.has_permission("inventory.dispatch"):
        raise PermissionDenied()
    transfer = StockTransfer.objects.select_for_update().get(
        pk=transfer.pk, organization=ctx.organization
    )
    if transfer.status != TransferStatus.DRAFT:
        raise BusinessRuleViolation("Only a draft transfer can be approved.")
    transfer.status = TransferStatus.APPROVED
    transfer.save(update_fields=["status", "updated_at"])
    record_event(
        action="inventory.transfer_approved",
        actor=ctx.user,
        organization=ctx.organization,
        target=transfer,
        metadata={"number": transfer.number},
        request=request,
    )
    return transfer


@transaction.atomic
def dispatch_transfer(ctx, transfer: StockTransfer, *, request=None) -> StockTransfer:
    if not ctx.has_permission("inventory.dispatch"):
        raise PermissionDenied()
    transfer = (
        StockTransfer.objects.select_for_update()
        .select_related("source_location", "destination_location")
        .get(pk=transfer.pk, organization=ctx.organization)
    )
    if transfer.status != TransferStatus.APPROVED:
        raise BusinessRuleViolation("Approve the transfer before dispatch.")
    _, transit = ensure_brand_locations(ctx.organization)
    for line in transfer.lines.select_related("item"):
        qty = line.requested_quantity
        line.dispatched_quantity = qty
        line.save(update_fields=["dispatched_quantity", "updated_at"])
        base_qty = quantity_in_base(qty, line.unit, line.item)
        post_movement(
            ctx=ctx,
            location=transfer.source_location,
            item=line.item,
            quantity=-base_qty,
            reason=MovementReason.TRANSFER_OUT,
            reference_type="transfer",
            reference_id=transfer.pk,
            idempotency_key=f"transfer:{transfer.pk}:out:{line.pk}",
        )
        post_movement(
            ctx=ctx,
            location=transit,
            item=line.item,
            quantity=base_qty,
            reason=MovementReason.TRANSFER_IN,
            reference_type="transfer",
            reference_id=transfer.pk,
            idempotency_key=f"transfer:{transfer.pk}:transit:{line.pk}",
        )
    transfer.status = TransferStatus.DISPATCHED
    transfer.dispatched_at = timezone.now()
    transfer.dispatched_by = ctx.user
    transfer.save()
    from apps.branches.models import Branch

    branch = Branch.objects.filter(pk=transfer.destination_location.branch_id).first()
    if branch is not None and branch.login_user_id:
        notify_users(
            organization=ctx.organization,
            users=[branch.login_user],
            notification_type=NotificationType.TRANSFER_DISPATCHED,
            title=f"{transfer.number} is waiting for confirmation",
            body=f"Stock from the central kitchen is on the way to {branch.name}.",
            link_path="/transfers",
        )
    record_event(
        action="inventory.transfer_dispatched",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=transfer,
        metadata={"number": transfer.number},
        request=request,
    )
    return transfer


@transaction.atomic
def receive_transfer(ctx, transfer: StockTransfer, data: dict, *, request=None) -> StockTransfer:
    transfer = (
        StockTransfer.objects.select_for_update()
        .select_related("destination_location", "source_location")
        .get(pk=transfer.pk, organization=ctx.organization)
    )
    from apps.branches.models import Branch

    branch = Branch.objects.filter(pk=transfer.destination_location.branch_id).first()
    if branch is None or not (
        ctx.has_permission("inventory.receive")
        or ctx.has_permission("inventory.receive", branch.pk)
    ):
        raise PermissionDenied()
    if transfer.status != TransferStatus.DISPATCHED:
        raise BusinessRuleViolation("This transfer is not waiting for receipt.")
    _, transit = ensure_brand_locations(ctx.organization)
    incoming = {str(row["line_id"]): row for row in data["lines"]}
    lines = list(transfer.lines.select_related("item"))
    if {str(line.pk) for line in lines} != set(incoming):
        raise ValidationError({"lines": ["Confirm every line on the transfer."]})
    short = False
    for line in lines:
        row = incoming[str(line.pk)]
        received = Decimal(row["received_quantity"])
        if received < 0 or received > line.dispatched_quantity:
            raise ValidationError(
                {"lines": ["Received quantity cannot exceed the dispatched quantity."]}
            )
        line.received_quantity = received
        line.discrepancy_note = (row.get("note") or "").strip()
        line.save(update_fields=["received_quantity", "discrepancy_note", "updated_at"])
        if received != line.dispatched_quantity:
            short = True
        if received > 0:
            base_qty = quantity_in_base(received, line.unit, line.item)
            post_movement(
                ctx=ctx,
                location=transit,
                item=line.item,
                quantity=-base_qty,
                reason=MovementReason.TRANSFER_OUT,
                reference_type="transfer",
                reference_id=transfer.pk,
                idempotency_key=f"transfer:{transfer.pk}:leave-transit:{line.pk}",
            )
            post_movement(
                ctx=ctx,
                location=transfer.destination_location,
                item=line.item,
                quantity=base_qty,
                reason=MovementReason.TRANSFER_IN,
                reference_type="transfer",
                reference_id=transfer.pk,
                idempotency_key=f"transfer:{transfer.pk}:branch:{line.pk}",
            )
    transfer.status = (
        TransferStatus.PARTIALLY_RECEIVED if short else TransferStatus.RECEIVED
    )
    transfer.received_at = timezone.now()
    transfer.received_by = ctx.user
    transfer.save()
    if short:
        notify_users(
            organization=ctx.organization,
            users=brand_admin_users(ctx.organization),
            notification_type=NotificationType.TRANSFER_DISCREPANCY,
            title=f"{transfer.number} has a delivery discrepancy",
            body=f"{branch.name} confirmed a quantity that differs from the dispatch.",
            link_path="/transfers",
        )
        settings_row = get_or_create_settings(ctx.organization)
        recipients = settings_row.recipient_emails()
        if recipients:
            from apps.notifications.mail import send_system_email

            send_system_email(
                subject=f"{transfer.number} delivery discrepancy",
                message=(
                    f"{branch.name} confirmed {transfer.number} with a quantity "
                    "that differs from what the kitchen dispatched. The original dispatch was kept."
                ),
                recipients=recipients,
            )
    record_event(
        action="inventory.transfer_received",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=transfer,
        metadata={
            "number": transfer.number,
            "status": transfer.status,
            "lines": [
                {
                    "item": line.item.sku,
                    "dispatched": str(line.dispatched_quantity),
                    "received": str(line.received_quantity),
                }
                for line in lines
            ],
        },
        request=request,
    )
    return transfer


@transaction.atomic
def close_transfer(ctx, transfer: StockTransfer, *, request=None) -> StockTransfer:
    if not ctx.has_permission("inventory.adjust"):
        raise PermissionDenied()
    transfer = StockTransfer.objects.select_for_update().get(
        pk=transfer.pk, organization=ctx.organization
    )
    if transfer.status not in (TransferStatus.RECEIVED, TransferStatus.PARTIALLY_RECEIVED):
        raise BusinessRuleViolation("Receive the transfer before closing it.")
    transfer.status = TransferStatus.CLOSED
    transfer.save(update_fields=["status", "updated_at"])
    record_event(
        action="inventory.transfer_closed",
        actor=ctx.user,
        organization=ctx.organization,
        target=transfer,
        metadata={"number": transfer.number},
        request=request,
    )
    return transfer


@transaction.atomic
def adjust_stock(ctx, data: dict, *, request=None) -> StockMovement:
    if not ctx.has_permission("inventory.adjust"):
        raise PermissionDenied()
    location = InventoryLocation.objects.filter(
        organization=ctx.organization, pk=data["location_id"]
    ).first()
    item = Item.objects.filter(organization=ctx.organization, pk=data["item_id"]).first()
    if location is None or item is None:
        raise ValidationError({"location_id": ["Unknown location or item."]})
    if not item.tracks_stock:
        raise ValidationError({"item_id": ["Turn on stock tracking for this item before changing its quantity."]})
    signed = quantity_in_base(abs(Decimal(data["quantity"])), data["unit"], item)
    if data["direction"] == "out":
        signed = -signed
    before = (
        StockBalance.objects.filter(location=location, item=item)
        .values_list("quantity", flat=True)
        .first()
        or Decimal("0")
    )
    movement = post_movement(
        ctx=ctx,
        location=location,
        item=item,
        quantity=signed,
        reason=data["reason"],
        reference_type="adjustment",
        note=data.get("note") or "",
    )
    record_event(
        action="inventory.adjusted",
        actor=ctx.user,
        organization=ctx.organization,
        target=movement,
        metadata={
            "item": item.sku,
            "location": location.name,
            "before": str(before),
            "change": str(signed),
            "reason": data["reason"],
            "note": data.get("note") or "",
        },
        request=request,
    )
    return movement


def sale_deductions(ctx, *, sale, location, lines):
    """Deduct a sale once.

    Lines marked for sale are made to order and consume ingredients.
    A recipe with no sale lines was produced in advance, so the sale takes the finished item.
    The same ingredients are never consumed in both places.
    """
    for line in lines:
        recipe = effective_recipe(ctx.organization, line["item"])
        scale = _scale(recipe, Decimal(line["quantity"]))
        made_to_order = recipe.lines.filter(consume_at=ConsumeAt.SALE).exists()
        if made_to_order:
            _consume_lines(
                ctx,
                recipe=recipe,
                location=location,
                scale=scale,
                consume_at=ConsumeAt.SALE,
                reference_type="sale",
                reference_id=sale.pk,
                reason=MovementReason.SALE,
            )
        elif line["item"].tracks_stock:
            post_movement(
                ctx=ctx,
                location=location,
                item=line["item"],
                quantity=-quantity_in_base(line["quantity"], line["item"].base_unit, line["item"]),
                reason=MovementReason.SALE,
                reference_type="sale",
                reference_id=sale.pk,
                idempotency_key=f"sale:{sale.pk}:item:{line['item'].pk}",
            )
        line["recipe"] = recipe
    return lines


def reverse_document(ctx, *, reference_type: str, reference_id, reason: str):
    movements = StockMovement.objects.filter(
        organization=ctx.organization,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=MovementReason.SALE,
    ).select_related("location", "item")
    for movement in movements:
        post_movement(
            ctx=ctx,
            location=movement.location,
            item=movement.item,
            quantity=-movement.quantity,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=f"reverse:{movement.pk}",
        )
