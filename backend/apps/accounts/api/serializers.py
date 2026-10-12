from rest_framework import serializers

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "full_name", "date_joined")
        read_only_fields = fields


class MeSerializer(UserSerializer):
    platform_permissions = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = (*UserSerializer.Meta.fields, "platform_permissions")
        read_only_fields = fields

    def get_platform_permissions(self, user) -> list[str]:
        from apps.access_control.services import platform_permissions_for

        return sorted(platform_permissions_for(user))


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class SessionSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = MeSerializer()


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField()


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
