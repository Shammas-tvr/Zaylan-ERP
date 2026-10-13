from rest_framework import serializers

from ..models import Item, Recipe, RecipeLine


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = (
            "id",
            "sku",
            "name",
            "kind",
            "base_unit",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        validators: list = []


class ItemWriteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=["RAW", "PACKAGING", "SEMI", "FINISHED"])
    base_unit = serializers.ChoiceField(choices=["G", "ML", "EACH"])
    is_active = serializers.BooleanField(required=False)


class RecipeLineSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    ingredient_sku = serializers.CharField(source="ingredient.sku", read_only=True)

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
        )


class RecipeSerializer(serializers.ModelSerializer):
    output_name = serializers.CharField(source="output_item.name", read_only=True)
    lines = RecipeLineSerializer(many=True, read_only=True)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "output_item",
            "output_name",
            "version",
            "effective_from",
            "yield_quantity",
            "is_active",
            "lines",
            "created_at",
        )


class RecipeLineWriteSerializer(serializers.Serializer):
    ingredient_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=["G", "KG", "ML", "L", "EACH"])
    consume_at = serializers.ChoiceField(choices=["PRODUCTION", "SALE"])


class RecipeWriteSerializer(serializers.Serializer):
    output_item_id = serializers.UUIDField()
    effective_from = serializers.DateField()
    yield_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    lines = RecipeLineWriteSerializer(many=True)
