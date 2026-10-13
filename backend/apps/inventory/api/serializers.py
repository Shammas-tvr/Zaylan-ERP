from rest_framework import serializers

from ..models import (
    InventoryLocation,
    ProductionOrder,
    StockBalance,
    StockTransfer,
    StockTransferLine,
)


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLocation
        fields = ("id", "kind", "name", "branch")


class BalanceSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name")
    item_sku = serializers.CharField(source="item.sku")
    item_kind = serializers.CharField(source="item.kind")
    category = serializers.CharField(source="item.category")
    base_unit = serializers.CharField(source="item.base_unit")
    stock_unit = serializers.CharField(source="item.stock_unit")
    minimum_stock = serializers.DecimalField(source="item.minimum_stock", max_digits=14, decimal_places=3)
    expiry_date = serializers.DateField(source="item.expiry_date", allow_null=True)
    location_name = serializers.CharField(source="location.name")
    location_kind = serializers.CharField(source="location.kind")

    class Meta:
        model = StockBalance
        fields = (
            "id",
            "location",
            "location_name",
            "location_kind",
            "item",
            "item_name",
            "item_sku",
            "item_kind",
            "category",
            "base_unit",
            "stock_unit",
            "minimum_stock",
            "expiry_date",
            "quantity",
        )


class ProductionSerializer(serializers.ModelSerializer):
    recipe_name = serializers.CharField(source="recipe.output_item.name", read_only=True)

    class Meta:
        model = ProductionOrder
        fields = (
            "id",
            "recipe",
            "recipe_name",
            "planned_quantity",
            "actual_quantity",
            "waste_quantity",
            "status",
            "completed_at",
            "created_at",
        )


class ProductionWriteSerializer(serializers.Serializer):
    recipe_id = serializers.UUIDField()
    planned_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)


class ProductionCompleteSerializer(serializers.Serializer):
    actual_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    waste_quantity = serializers.DecimalField(
        max_digits=14, decimal_places=3, required=False, default=0
    )


class TransferLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_sku = serializers.CharField(source="item.sku", read_only=True)

    class Meta:
        model = StockTransferLine
        fields = (
            "id",
            "item",
            "item_name",
            "item_sku",
            "unit",
            "requested_quantity",
            "dispatched_quantity",
            "received_quantity",
            "discrepancy_note",
        )


class TransferSerializer(serializers.ModelSerializer):
    lines = TransferLineSerializer(many=True, read_only=True)
    destination_name = serializers.CharField(source="destination_location.name", read_only=True)
    source_name = serializers.CharField(source="source_location.name", read_only=True)
    branch_id = serializers.UUIDField(source="destination_location.branch_id", read_only=True)

    class Meta:
        model = StockTransfer
        fields = (
            "id",
            "number",
            "status",
            "destination_name",
            "source_name",
            "branch_id",
            "dispatched_at",
            "received_at",
            "lines",
            "created_at",
        )


class TransferLineWriteSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=["G", "KG", "ML", "L", "EACH", "BOX"])


class TransferWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    source_location_id = serializers.UUIDField(required=False)
    lines = TransferLineWriteSerializer(many=True)


class ReceiveLineSerializer(serializers.Serializer):
    line_id = serializers.UUIDField()
    received_quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ReceiveSerializer(serializers.Serializer):
    lines = ReceiveLineSerializer(many=True)


class MovementSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    item_name = serializers.CharField(source="item.name")
    item_sku = serializers.CharField(source="item.sku")
    location_name = serializers.CharField(source="location.name")
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    base_unit = serializers.CharField(source="item.base_unit")
    stock_unit = serializers.CharField(source="item.stock_unit")
    reason = serializers.CharField()
    note = serializers.CharField()


class AdjustmentSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    unit = serializers.ChoiceField(choices=["G", "KG", "ML", "L", "EACH", "BOX"])
    direction = serializers.ChoiceField(choices=["in", "out"])
    reason = serializers.ChoiceField(choices=["WASTAGE", "EXPIRY", "ADJUSTMENT"])
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
