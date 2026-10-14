from django.db import models
from django.db.models.functions import Upper

from apps.core.models import TimeStampedModel


class ItemKind(models.TextChoices):
    RAW = "RAW", "Ingredient"
    PACKAGING = "PACKAGING", "Packaging"
    SEMI = "SEMI", "Semi-finished product"
    FINISHED = "FINISHED", "Finished product"
    RESALE = "RESALE", "Purchased resale item"


class BaseUnit(models.TextChoices):
    G = "G", "Grams"
    ML = "ML", "Millilitres"
    EACH = "EACH", "Each"


class ConsumeAt(models.TextChoices):
    PRODUCTION = "PRODUCTION", "During production"
    SALE = "SALE", "When sold"


class CostingMethod(models.TextChoices):
    MOVING_AVERAGE = "MOVING_AVERAGE", "Moving weighted average"
    FIFO = "FIFO", "FIFO"


class StockUnit(models.TextChoices):
    G = "G", "Gram"
    KG = "KG", "Kilogram"
    ML = "ML", "Millilitre"
    L = "L", "Litre"
    EACH = "EACH", "Piece"
    BOX = "BOX", "Box"
    PACKET = "PACKET", "Packet"
    BOTTLE = "BOTTLE", "Bottle"
    TRAY = "TRAY", "Tray"


class Item(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="items"
    )
    sku = models.CharField(max_length=32)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=16, choices=ItemKind.choices)
    category = models.CharField(max_length=80, blank=True)
    base_unit = models.CharField(max_length=8, choices=BaseUnit.choices)
    stock_unit = models.CharField(max_length=8, choices=StockUnit.choices, default=StockUnit.G)
    purchase_unit = models.CharField(max_length=8, choices=StockUnit.choices, blank=True)
    purchase_factor = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    supplier_name = models.CharField(max_length=150, blank=True)
    default_supplier = models.ForeignKey(
        "Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_items",
    )
    suppliers = models.ManyToManyField("Supplier", blank=True, related_name="items")
    costing_method = models.CharField(
        max_length=24, choices=CostingMethod.choices, default=CostingMethod.MOVING_AVERAGE
    )
    standard_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    minimum_stock = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    storage_location = models.ForeignKey(
        "inventory.InventoryLocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stored_items",
    )
    tracks_batch = models.BooleanField(default=False)
    tracks_expiry = models.BooleanField(default=False)
    expiry_date = models.DateField(null=True, blank=True)
    tracks_stock = models.BooleanField(default=True)
    image_key = models.CharField(max_length=300, blank=True)
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


class Supplier(TimeStampedModel):
    """A brand's supplier. Items point here instead of copying contact details."""

    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="suppliers"
    )
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "organization", Upper("name"), name="catalog_supplier_org_name_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ItemLocationPolicy(TimeStampedModel):
    """Where an item may be stocked, and the low-stock threshold in the item's stock unit."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="location_policies")
    location = models.ForeignKey(
        "inventory.InventoryLocation", on_delete=models.CASCADE, related_name="item_policies"
    )
    minimum_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "location"], name="catalog_item_location_policy_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item} @ {self.location}"


class RecipeStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"


class Recipe(TimeStampedModel):
    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="recipes"
    )
    output_item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="recipes")
    version = models.PositiveIntegerField()
    effective_from = models.DateField()
    yield_quantity = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    expected_waste_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    product = models.ForeignKey(
        "Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipes",
    )
    status = models.CharField(
        max_length=16, choices=RecipeStatus.choices, default=RecipeStatus.CONFIRMED
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"], name="catalog_recipe_line_ingredient_unique"
            ),
        ]


class Product(TimeStampedModel):
    """What the brand sells. Stock and the recipe stay on the linked inventory item."""

    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="products"
    )
    sku = models.CharField(max_length=32)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    image_key = models.CharField(max_length=300, blank=True)
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    labour_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    overhead_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sale_unit = models.CharField(max_length=8, choices=StockUnit.choices, default=StockUnit.EACH)
    kind = models.CharField(max_length=16, choices=ItemKind.choices, default=ItemKind.FINISHED)
    inventory_item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
    )
    is_active = models.BooleanField(default=True)
    branches = models.ManyToManyField("branches.Branch", blank=True, related_name="products")

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "organization", Upper("sku"), name="catalog_product_org_sku_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.name
