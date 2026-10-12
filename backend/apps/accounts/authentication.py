from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class ZaylanJWTAuthentication(JWTAuthentication):
    """Rejects access tokens issued before the user's most recent password change."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        issued_at = validated_token.get("iat")
        if user.password_changed_at and issued_at is not None:
            if int(issued_at) < int(user.password_changed_at.timestamp()):
                raise AuthenticationFailed("Token is no longer valid.", code="token_not_valid")
        return user
