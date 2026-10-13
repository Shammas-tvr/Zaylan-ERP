from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit_logs.services import record_event
from apps.branches.models import Branch
from apps.catalog.models import Item, ItemKind
from apps.core.exceptions import BusinessRuleViolation
from apps.inventory.models import MovementReason
from apps.inventory.services import ensure_branch_location, reverse_document, sale_deductions

from .models import Sale, SaleLine, SaleStatus


def _branch_for_sale(ctx, branch_id) -> Branch:
    branch = Branch.objects.filter(organization=ctx.organization, pk=branch_id).first()
    if branch is None or not (
        ctx.has_permission("pos.sell") or ctx.has_permission("pos.sell", branch.pk)
    ):
        raise PermissionDenied()
    return branch


@transaction.atomic
def record_sale(ctx, data: dict, *, request=None) -> Sale:
    key = (data.get("idempotency_key") or "").strip()
    if not key:
        raise ValidationError({"idempotency_key": ["A sale needs an idempotency key."]})
    existing = (
        Sale.objects.filter(organization=ctx.organization, idempotency_key=key)
        .prefetch_related("lines")
        .first()
    )
    if existing is not None:
        return existing
    branch = _branch_for_sale(ctx, data["branch_id"])
    location = ensure_branch_location(branch)
    prepared = []
    for row in data["lines"]:
        item = Item.objects.filter(
            organization=ctx.organization, pk=row["item_id"], is_active=True
        ).first()
        if item is None or item.kind != ItemKind.FINISHED:
            raise ValidationError({"lines": ["Sell a finished product."]})
        prepared.append({"item": item, "quantity": Decimal(row["quantity"])})
    if not prepared:
        raise ValidationError({"lines": ["Add at least one product."]})
    try:
        with transaction.atomic():
            sale = Sale.objects.create(
                organization=ctx.organization,
                branch=branch,
                location=location,
                idempotency_key=key,
                actor=ctx.user,
                status=SaleStatus.COMPLETED,
            )
    except IntegrityError:
        return Sale.objects.get(organization=ctx.organization, idempotency_key=key)
    prepared = sale_deductions(ctx, sale=sale, location=location, lines=prepared)
    SaleLine.objects.bulk_create(
        [
            SaleLine(
                sale=sale,
                item=row["item"],
                recipe=row["recipe"],
                quantity=row["quantity"],
            )
            for row in prepared
        ]
    )
    record_event(
        action="sales.completed",
        actor=ctx.user,
        organization=ctx.organization,
        branch=branch,
        target=sale,
        metadata={"idempotency_key": key, "lines": len(prepared)},
        request=request,
    )
    return sale


@transaction.atomic
def reverse_sale(ctx, sale: Sale, *, status: str, request=None) -> Sale:
    sale = Sale.objects.select_for_update().select_related("branch").get(
        pk=sale.pk, organization=ctx.organization
    )
    if not (
        ctx.has_permission("pos.refund") or ctx.has_permission("pos.refund", sale.branch_id)
    ):
        raise PermissionDenied()
    if sale.status != SaleStatus.COMPLETED:
        raise BusinessRuleViolation("Only a completed sale can be reversed.")
    reverse_document(
        ctx,
        reference_type="sale",
        reference_id=sale.pk,
        reason=MovementReason.SALE_REVERSAL,
    )
    sale.status = status
    sale.save(update_fields=["status", "updated_at"])
    record_event(
        action="sales.reversed",
        actor=ctx.user,
        organization=ctx.organization,
        branch=sale.branch,
        target=sale,
        metadata={"status": status},
        request=request,
    )
    return sale
