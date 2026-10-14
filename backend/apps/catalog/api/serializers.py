from decimal import Decimal

from rest_framework import serializers

from apps.core.storage import image_url

from ..models import Item, ItemLocationPolicy, Product, Recipe, RecipeLine, Supplier
from ..services import product_estimate
from ..units import from_base, quantity_in_base, stock_factor

UNIT_CHOICES = ["G", "KG", "ML", "L", "EACH", "BOX", "PACKET", "BOTTLE", "TRAY"]
KIND_CHOICES = ["RAW", "PACKAGING", "SEMI", "FINISHED", "RESALE"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ("id", "name", "is_active")
        read_only_fields = ("id", "is_active")


class ItemPolicySerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = ItemLocationPolicy
        fields = ("location", "location_name", "minimum_quantity")


class StockPolicyWriteSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()
    minimum_quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0"))


class ItemSerializer(serializers.ModelSerializer):
    storage_location_name = serializers.CharField(source="storage_location.name", read_only=True)
    default_supplier_name = serializers.SerializerMethodField()
    supplier_ids = serializers.SerializerMethodField()
    stock_policies = ItemPolicySerializer(source="location_policies", many=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    branch_quantity = serializers.SerializerMethodField()
    branch_minimum = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = (
            "id",
            "sku",
            "name",
            "kind",
            "category",
            "base_unit",
            "stock_unit",
            "purchase_unit",
            "purchase_factor",
            "supplier_name",
            "default_supplier",
            "default_supplier_name",
            "supplier_ids",
            "stock_policies",
            "costing_method",
            "standard_cost",
            "minimum_stock",
            "storage_location",
            "storage_location_name",
            "branch_quantity",
            "branch_minimum",
            "stock_status",
            "tracks_batch",
            "tracks_expiry",
            "expiry_date",
            "tracks_stock",
            "image_key",
            "image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "base_unit", "sku")
        validators: list = []

    def get_image_url(self, item):
        return image_url(item.image_key)

    def get_default_supplier_name(self, item):
        return item.default_supplier.name if item.default_supplier_id else None

    def get_supplier_ids(self, item) -> list[str]:
        return [str(row.pk) for row in item.suppliers.all()]

    def get_branch_quantity(self, item):
        if not self.context.get("stock_location"):
            return None
        raw = getattr(item, "branch_quantity_base", None)
        minimum = getattr(item, "branch_minimum", None)
        if raw is None:
            return "0.000" if minimum is not None else None
        return str(from_base(raw, item))

    def get_branch_minimum(self, item):
        if not self.context.get("stock_location"):
            return None
        minimum = getattr(item, "branch_minimum", None)
        return None if minimum is None else str(minimum)

    def get_stock_status(self, item):
        if not self.context.get("stock_location"):
            return None
        minimum = getattr(item, "branch_minimum", None)
        if minimum is None:
            return "unstocked"
        quantity = Decimal(self.get_branch_quantity(item) or 0)
        if quantity <= 0:
            return "out"
        if quantity <= Decimal(minimum):
            return "low"
        return "normal"


class ItemWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=KIND_CHOICES)
    category = serializers.CharField(max_length=80, required=False, allow_blank=True)
    base_unit = serializers.ChoiceField(choices=["G", "ML", "EACH"], required=False)
    stock_unit = serializers.ChoiceField(choices=UNIT_CHOICES, required=False)
    purchase_unit = serializers.ChoiceField(choices=UNIT_CHOICES, required=False)
    purchase_factor = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    supplier_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    default_supplier_id = serializers.UUIDField(required=False, allow_null=True)
    supplier_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    stock_policies = StockPolicyWriteSerializer(many=True, required=False)
    costing_method = serializers.ChoiceField(
        choices=["MOVING_AVERAGE", "FIFO"], required=False
    )
    standard_cost = serializers.DecimalField(max_digits=14, decimal_places=4, required=False)
    minimum_stock = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    storage_location_id = serializers.UUIDField(required=False, allow_null=True)
    tracks_batch = serializers.BooleanField(required=False)
    tracks_expiry = serializers.BooleanField(required=False)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    tracks_stock = serializers.BooleanField(required=False)
    image_key = serializers.CharField(max_length=300, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if self.partial:
            return attrs
        if not attrs.get("stock_unit") and not attrs.get("base_unit"):
            raise serializers.ValidationError({"stock_unit": ["Choose a unit."]})
        return attrs


class RecipeLineSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    ingredient_sku = serializers.CharField(source="ingredient.sku", read_only=True)
    line_cost = serializers.SerializerMethodField()

    class Meta:
        model = RecipeLine
        fields = (
            "id",
            "ingredient",
            "ingredient_name",
            "ingredient_sku",
            "quantity",
            "unit",
            "consume_at",
            "line_cost",
            "nested_recipe",
        )

    nested_recipe = serializers.SerializerMethodField()

    def get_nested_recipe(self, line):
        child = (
            line.ingredient.recipes.filter(is_active=True)
            .exclude(pk=line.recipe_id)
            .order_by("-effective_from", "-version")
            .first()
        )
        if child is None:
            return None
        return {"id": str(child.pk), "version": child.version, "output_name": line.ingredient.name}

    def get_line_cost(self, line) -> str:
        base = quantity_in_base(line.quantity, line.unit, line.ingredient)
        factor = stock_factor(line.ingredient.stock_unit or line.ingredient.base_unit)
        per_base = Decimal(line.ingredient.standard_cost) / factor
        return str((base * per_base).quantize(Decimal("0.01")))


class RecipeSerializer(serializers.ModelSerializer):
    output_name = serializers.CharField(source="output_item.name", read_only=True)
    product_name = serializers.SerializerMethodField()
    lines = RecipeLineSerializer(many=True, read_only=True)
    ingredient_cost = serializers.SerializerMethodField()
    ingredient_cost_per_unit = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            "id",
            "output_item",
            "output_name",
            "product",
            "product_name",
            "version",
            "effective_from",
            "yield_quantity",
            "expected_waste_percent",
            "status",
            "is_active",
            "lines",
            "ingredient_cost",
            "ingredient_cost_per_unit",
            "created_at",
        )

    def get_product_name(self, recipe) -> str:
        if recipe.product_id:
            return recipe.product.name
        return recipe.output_item.name

    def get_ingredient_cost(self, recipe) -> str:
        total = Decimal("0")
        for line in recipe.lines.all():
            total += Decimal(RecipeLineSerializer(line).data["line_cost"])
        return str(total.quantize(Decimal("0.01")))

    def get_ingredient_cost_per_unit(self, recipe) -> str:
        from ..services import ingredient_cost_per_unit

        return str(ingredient_cost_per_unit(recipe))


class RecipeLineWriteSerializer(serializers.Serializer):
    ingredient_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=UNIT_CHOICES)
    consume_at = serializers.ChoiceField(choices=["PRODUCTION", "SALE"])


class RecipeWriteSerializer(serializers.Serializer):
    output_item_id = serializers.UUIDField(required=False)
    product_id = serializers.UUIDField(required=False)
    effective_from = serializers.DateField()
    yield_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    expected_waste_percent = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, default=0
    )
    status = serializers.ChoiceField(choices=["DRAFT", "CONFIRMED"], required=False)
    lines = RecipeLineWriteSerializer(many=True)

    def validate(self, attrs):
        if not attrs.get("product_id") and not attrs.get("output_item_id"):
            raise serializers.ValidationError({"product_id": ["Choose a product or an output item."]})
        return attrs


class ProductSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    branch_ids = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    costing = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "category",
            "description",
            "image_key",
            "image_url",
            "selling_price",
            "labour_cost",
            "overhead_cost",
            "sale_unit",
            "kind",
            "inventory_item",
            "inventory_item_name",
            "branch_ids",
            "is_active",
            "costing",
            "created_at",
        )

    def get_branch_ids(self, product) -> list[str]:
        return [str(branch.pk) for branch in product.branches.all()]

    def get_image_url(self, product):
        return image_url(product.image_key)

    def get_costing(self, product) -> dict:
        return product_estimate(product)


class ProductWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    name = serializers.CharField(max_length=150)
    category = serializers.CharField(max_length=80, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    image_key = serializers.CharField(max_length=300, required=False, allow_blank=True)
    selling_price = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    labour_cost = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    overhead_cost = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    sale_unit = serializers.ChoiceField(choices=UNIT_CHOICES, required=False)
    kind = serializers.ChoiceField(choices=["RAW", "PACKAGING", "SEMI", "FINISHED", "RESALE"], required=False)
    inventory_item_id = serializers.UUIDField(required=False, allow_null=True)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if self.partial:
            return attrs
        if not (attrs.get("category") or "").strip():
            raise serializers.ValidationError({"category": ["Enter a category."]})
        price = attrs.get("selling_price")
        kind = attrs.get("kind") or "FINISHED"
        if kind in {"FINISHED", "RESALE"} and (price is None or Decimal(price) <= 0):
            raise serializers.ValidationError({"selling_price": ["Enter a selling price for this product."]})
        return attrs
