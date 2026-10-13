from django.db import models
from django.db.models.functions import Upper

from apps.core.models import TimeStampedModel


class ItemKind(models.TextChoices):
    RAW = "RAW", "Raw material"
    PACKAGING = "PACKAGING", "Packaging"
    SEMI = "SEMI", "Semi-finished"
    FINISHED = "FINISHED", "Finished product"


class BaseUnit(models.TextChoices):
    G = "G", "Grams"
    ML = "ML", "Millilitres"
    EACH = "EACH", "Each"


class ConsumeAt(models.TextChoices):
    PRODUCTION = "PRODUCTION", "During production"
    SALE = "SALE", "When sold"


class Item(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="items"
    )
    sku = models.CharField(max_length=32)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=16, choices=ItemKind.choices)
    base_unit = models.CharField(max_length=8, choices=BaseUnit.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "organization", Upper("sku"), name="catalog_item_org_sku_unique"
            ),
        ]
        indexes = [models.Index(fields=["organization", "kind", "is_active"])]

    def __str__(self) -> str:
        return self.name


class Recipe(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="recipes"
    )
    output_item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="recipes")
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    yield_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-effective_from", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "output_item", "version"],
                name="catalog_recipe_org_item_version_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.output_item} v{self.version}"


class RecipeLine(TimeStampedModel):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="lines")
    ingredient = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="used_in")
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=8)
    consume_at = models.CharField(max_length=16, choices=ConsumeAt.choices)

    class Meta:
        ordering = ["consume_at", "created_at"]
