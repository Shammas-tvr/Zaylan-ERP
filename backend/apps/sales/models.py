from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class SaleStatus(models.TextChoices):
    COMPLETED = "COMPLETED", "Completed"
    VOIDED = "VOIDED", "Voided"
    REFUNDED = "REFUNDED", "Refunded"


class Sale(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="sales"
    )
    branch = models.ForeignKey("branches.Branch", on_delete=models.PROTECT, related_name="sales")
    location = models.ForeignKey(
        "inventory.InventoryLocation", on_delete=models.PROTECT, related_name="sales"
    )
    status = models.CharField(
        max_length=16, choices=SaleStatus.choices, default=SaleStatus.COMPLETED
    )
    idempotency_key = models.CharField(max_length=80)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "idempotency_key"],
                name="sales_sale_org_idempotency_unique",
            ),
        ]


class SaleLine(TimeStampedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey("catalog.Item", on_delete=models.PROTECT, related_name="sale_lines")
    recipe = models.ForeignKey(
        "catalog.Recipe", on_delete=models.PROTECT, related_name="sale_lines"
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
