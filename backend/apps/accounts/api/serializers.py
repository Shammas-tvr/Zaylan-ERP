from rest_framework import serializers

from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "full_name", "date_joined")
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
    # Accept email (Brand Admin) or username (brand staff). ``email`` kept for compatibility.
    identifier = serializers.CharField(max_length=254, required=False, allow_blank=True)
    email = serializers.CharField(max_length=254, required=False, allow_blank=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        identifier = (attrs.get("identifier") or attrs.get("email") or "").strip()
        if not identifier:
            raise serializers.ValidationError({"identifier": ["Email or username is required."]})
        attrs["identifier"] = identifier
        return attrs


class SessionSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = MeSerializer()


class AccessTokenSerializer(serializers.Serializer):
    access = serializers.CharField()


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class BrandPortalSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.SlugField()
    masked_admin_email = serializers.CharField(allow_blank=True)


class PasswordForgotSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=63)


class PasswordResetSerializer(serializers.Serializer):
    slug = serializers.SlugField(max_length=63)
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(max_length=128, min_length=6, trim_whitespace=False)


class ProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
