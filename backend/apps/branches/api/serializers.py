from rest_framework import serializers

from ..models import Branch


class BranchSerializer(serializers.ModelSerializer):
    login_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    login_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.SerializerMethodField()

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
            "username",
            "login_username",
            "login_password",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "username", "created_at", "updated_at")
        # Uniqueness is checked inside the tenant by the service layer.
        validators: list = []

    def get_username(self, branch: Branch) -> str:
        user = getattr(branch, "login_user", None)
        return user.username if user and user.username else ""


class BranchMemberSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField(source="membership.id")
    full_name = serializers.CharField(source="membership.user.full_name")
    email = serializers.EmailField(source="membership.user.email")
    status = serializers.CharField(source="membership.status")
