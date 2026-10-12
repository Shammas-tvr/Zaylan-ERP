from rest_framework import serializers

from ..models import Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("code", "name", "module", "description")
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "key",
            "name",
            "description",
            "is_system",
            "permission_codes",
            "member_count",
        )
        read_only_fields = fields

    def get_permission_codes(self, role) -> list[str]:
        return sorted(rp.permission.code for rp in role.role_permissions.all())

    def get_member_count(self, role) -> int:
        return role.assignments.count()


class RoleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default=""
    )
    permission_codes = serializers.ListField(
        child=serializers.CharField(max_length=100), allow_empty=False
    )
