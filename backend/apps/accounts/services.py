from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenBackendError, TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit_logs.services import record_event
from apps.core.validators import normalize_email


def is_trusted_origin(request) -> bool:
    """Cookie-authenticated endpoints only accept requests from configured frontend origins."""
    allowed = set(settings.AUTH_TRUSTED_ORIGINS)
    origin = request.headers.get("Origin")
    if origin:
        return origin in allowed
    referer = request.headers.get("Referer")
    if referer:
        parts = urlsplit(referer)
        return f"{parts.scheme}://{parts.netloc}" in allowed
    return False


def set_refresh_cookie(response, raw_refresh: str) -> None:
    cookie = settings.AUTH_REFRESH_COOKIE
    response.set_cookie(
        cookie["NAME"],
        raw_refresh,
        max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=cookie["SECURE"],
        samesite=cookie["SAMESITE"],
        path=cookie["PATH"],
        domain=cookie["DOMAIN"],
    )


def clear_refresh_cookie(response) -> None:
    cookie = settings.AUTH_REFRESH_COOKIE
    response.delete_cookie(
        cookie["NAME"], path=cookie["PATH"], domain=cookie["DOMAIN"], samesite=cookie["SAMESITE"]
    )


def read_refresh_cookie(request) -> str | None:
    return request.COOKIES.get(settings.AUTH_REFRESH_COOKIE["NAME"])


def authenticate_credentials(request, email: str, password: str):
    user = authenticate(request, username=normalize_email(email), password=password)
    if user is None:
        record_event(
            action="auth.login_failed", metadata={"email": normalize_email(email)}, request=request
        )
        raise AuthenticationFailed("Invalid email or password.", code="invalid_credentials")
    return user


def issue_tokens(user) -> tuple[str, str]:
    refresh = RefreshToken.for_user(user)
    if jwt_settings.UPDATE_LAST_LOGIN:
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
    return str(refresh.access_token), str(refresh)


def revoke_all_refresh_tokens(user) -> None:
    outstanding = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in outstanding], ignore_conflicts=True
    )


def _session_invalid() -> AuthenticationFailed:
    return AuthenticationFailed("Session expired. Sign in again.", code="session_invalid")


def rotate_refresh_token(raw_refresh: str | None, *, request=None) -> tuple[str, str, object]:
    """
    Exchange a refresh token for a new access/refresh pair. Presenting a token that was already
    rotated indicates theft, so every session of that user is revoked.
    """
    if not raw_refresh:
        raise AuthenticationFailed("No active session.", code="session_missing")
    try:
        # Verifies signature and expiry without simplejwt's blacklist check, so reuse is detectable.
        payload = token_backend.decode(raw_refresh, verify=True)
    except TokenBackendError as exc:
        raise _session_invalid() from exc
    if payload.get(jwt_settings.TOKEN_TYPE_CLAIM) != "refresh":
        raise _session_invalid()

    jti = payload.get(jwt_settings.JTI_CLAIM)
    user_id = payload.get(jwt_settings.USER_ID_CLAIM)
    User = get_user_model()
    reused = False
    with transaction.atomic():
        outstanding = OutstandingToken.objects.select_for_update().filter(jti=jti).first()
        if outstanding is None or BlacklistedToken.objects.filter(token=outstanding).exists():
            reused = True
            user = User.objects.filter(pk=user_id).first()
            if user is not None:
                revoke_all_refresh_tokens(user)
                record_event(
                    action="auth.refresh_token_reuse_detected", actor=user, request=request
                )
        else:
            user = User.objects.filter(pk=user_id, is_active=True).first()
            if user is not None:
                BlacklistedToken.objects.create(token=outstanding)
                access, refresh = issue_tokens(user)
    # Raised outside the transaction so the reuse revocation above is committed.
    if reused or user is None:
        raise _session_invalid()
    return access, refresh, user


def revoke_refresh_token(raw_refresh: str | None) -> None:
    if not raw_refresh:
        return
    try:
        RefreshToken(raw_refresh).blacklist()
    except TokenError:
        pass


@transaction.atomic
def change_password(user, *, current_password: str, new_password: str, request=None) -> None:
    if not user.check_password(current_password):
        raise ValidationError({"current_password": ["The current password is incorrect."]})
    validate_password(new_password, user)
    user.set_password(new_password)
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password", "password_changed_at"])
    revoke_all_refresh_tokens(user)
    record_event(action="auth.password_changed", actor=user, request=request)
