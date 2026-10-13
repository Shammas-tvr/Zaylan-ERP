from decimal import Decimal

from rest_framework import serializers

from ..models import Item, Product, Recipe, RecipeLine
from ..units import quantity_in_base, stock_factor

UNIT_CHOICES = ["G", "KG", "ML", "L", "EACH", "BOX"]


class ItemSerializer(serializers.ModelSerializer):
    storage_location_name = serializers.CharField(source="storage_location.name", read_only=True)

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
            "costing_method",
            "standard_cost",
            "minimum_stock",
            "storage_location",
            "storage_location_name",
            "tracks_batch",
            "tracks_expiry",
            "expiry_date",
            "tracks_stock",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "base_unit")
        validators: list = []


class ItemWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=["RAW", "PACKAGING", "SEMI", "FINISHED"])
    category = serializers.CharField(max_length=80, required=False, allow_blank=True)
    base_unit = serializers.ChoiceField(choices=["G", "ML", "EACH"], required=False)
    stock_unit = serializers.ChoiceField(choices=UNIT_CHOICES, required=False)
    purchase_unit = serializers.ChoiceField(choices=UNIT_CHOICES, required=False)
    purchase_factor = serializers.DecimalField(max_digits=14, decimal_places=3, required=False)
    supplier_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
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
            "is_active",
            "lines",
            "ingredient_cost",
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
    lines = RecipeLineWriteSerializer(many=True)

    def validate(self, attrs):
        if not attrs.get("product_id") and not attrs.get("output_item_id"):
            raise serializers.ValidationError({"product_id": ["Choose a product or an output item."]})
        return attrs


class ProductSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(source="inventory_item.name", read_only=True)
    branch_ids = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "category",
            "selling_price",
            "sale_unit",
            "kind",
            "inventory_item",
            "inventory_item_name",
            "branch_ids",
            "is_active",
            "created_at",
        )

    def get_branch_ids(self, product) -> list[str]:
        return [str(branch_id) for branch_id in product.branches.values_list("id", flat=True)]


class ProductWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=32, required=False, allow_blank=True)
    name = serializers.CharField(max_length=150)
    category = serializers.CharField(max_length=80, required=False, allow_blank=True)
    selling_price = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    sale_unit = serializers.ChoiceField(choices=UNIT_CHOICES, required=False)
    kind = serializers.ChoiceField(choices=["RAW", "PACKAGING", "SEMI", "FINISHED"], required=False)
    inventory_item_id = serializers.UUIDField(required=False, allow_null=True)
    branch_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    is_active = serializers.BooleanField(required=False)
