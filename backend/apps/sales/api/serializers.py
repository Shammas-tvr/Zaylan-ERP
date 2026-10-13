from rest_framework import serializers

from ..models import Sale, SaleLine


class SaleLineSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = SaleLine
        fields = ("id", "item", "item_name", "quantity", "recipe")


class SaleSerializer(serializers.ModelSerializer):
    lines = SaleLineSerializer(many=True, read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Sale
        fields = (
            "id",
            "branch",
            "branch_name",
            "status",
            "idempotency_key",
            "lines",
            "created_at",
        )


class SaleLineWriteSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)


class SaleWriteSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    idempotency_key = serializers.CharField(max_length=80)
    lines = SaleLineWriteSerializer(many=True)
