from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class LocationKind(models.TextChoices):
    CENTRAL_KITCHEN = "CENTRAL_KITCHEN", "Central kitchen"
    BRANCH = "BRANCH", "Branch"
    IN_TRANSIT = "IN_TRANSIT", "In transit"


class MovementReason(models.TextChoices):
    PRODUCTION_CONSUME = "PRODUCTION_CONSUME", "Production consumption"
    PRODUCTION_OUTPUT = "PRODUCTION_OUTPUT", "Production output"
    PRODUCTION_WASTE = "PRODUCTION_WASTE", "Production waste"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfer out"
    TRANSFER_IN = "TRANSFER_IN", "Transfer in"
    SALE = "SALE", "Sale"
    SALE_REVERSAL = "SALE_REVERSAL", "Sale reversal"
    WASTAGE = "WASTAGE", "Wastage"
    EXPIRY = "EXPIRY", "Expiry"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"


class InventoryLocation(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="inventory_locations"
    )
    kind = models.CharField(max_length=24, choices=LocationKind.choices)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="inventory_location",
    )
    name = models.CharField(max_length=150)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "kind"],
                condition=models.Q(kind__in=["CENTRAL_KITCHEN", "IN_TRANSIT"]),
                name="inventory_location_singleton_unique",
            ),
            models.UniqueConstraint(
                fields=["branch"],
                condition=models.Q(branch__isnull=False),
                name="inventory_location_branch_unique",
            ),
        ]
        indexes = [models.Index(fields=["organization", "kind"])]

    def __str__(self) -> str:
        return self.name


class StockBalance(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="stock_balances"
    )
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="balances"
    )
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT, related_name="balances")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["location", "item"], name="inventory_balance_location_item_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="inventory_balance_non_negative"
            ),
        ]


class StockMovement(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="stock_movements"
    )
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="movements"
    )
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT, related_name="movements")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    reason = models.CharField(max_length=32, choices=MovementReason.choices)
    reference_type = models.CharField(max_length=32, blank=True)
    reference_id = models.UUIDField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    idempotency_key = models.CharField(max_length=200, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="inventory_movement_idempotency_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "location", "item"]),
            models.Index(fields=["reference_type", "reference_id"]),
        ]


class ProductionStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    COMPLETED = "COMPLETED", "Completed"


class ProductionOrder(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="production_orders"
    )
    location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="production_orders"
    )
    recipe = models.ForeignKey(
        "catalog.Recipe", on_delete=models.PROTECT, related_name="production_orders"
    )
    planned_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    actual_quantity = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    waste_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    status = models.CharField(
        max_length=16, choices=ProductionStatus.choices, default=ProductionStatus.DRAFT
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class TransferStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    APPROVED = "APPROVED", "Approved"
    DISPATCHED = "DISPATCHED", "Dispatched"
    RECEIVED = "RECEIVED", "Received"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially received"
    CLOSED = "CLOSED", "Closed"


class StockTransfer(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="stock_transfers"
    )
    number = models.CharField(max_length=20)
    source_location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="transfers_out"
    )
    destination_location = models.ForeignKey(
        InventoryLocation, on_delete=models.PROTECT, related_name="transfers_in"
    )
    status = models.CharField(
        max_length=24, choices=TransferStatus.choices, default=TransferStatus.DRAFT
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "number"], name="inventory_transfer_org_number_unique"
            ),
        ]


class StockTransferLine(TimeStampedModel):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT, related_name="+")
    unit = models.CharField(max_length=8)
    requested_quantity = models.DecimalField(max_digits=14, decimal_places=3)
    dispatched_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    received_quantity = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    discrepancy_note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transfer", "item"], name="inventory_transfer_line_item_unique"
            ),
        ]
