from rest_framework import serializers

from ..models import Branch


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = (
            "id",
            "code",
            "name",
            "status",
            "timezone",
            "phone",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        # Uniqueness is checked inside the tenant by the service layer.
        validators: list = []


class BranchMemberSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField(source="membership.id")
    full_name = serializers.CharField(source="membership.user.full_name")
    email = serializers.EmailField(source="membership.user.email")
    status = serializers.CharField(source="membership.status")
