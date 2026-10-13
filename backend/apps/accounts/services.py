import hashlib
import secrets
from datetime import timedelta
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
from apps.notifications.mail import send_system_email

from .models import PasswordResetOTP

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
STAFF_EMAIL_SUFFIX = ".staff.zaylan.local"


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


def authenticate_credentials(request, *, identifier: str, password: str, platform_only: bool = False):
    """
    Authenticate with email or username.
    When ``platform_only`` is True, the user must hold platform permissions (Super Admin login).
    When False, platform-only accounts are rejected (brand login).
    """
    from apps.access_control.services import platform_permissions_for

    raw = (identifier or "").strip()
    user = None
    if "@" in raw:
        user = authenticate(request, username=normalize_email(raw), password=password)
    else:
        candidate = get_user_model().objects.filter(username__iexact=raw, is_active=True).first()
        if candidate and candidate.check_password(password):
            user = candidate
    if user is None:
        record_event(
            action="auth.login_failed", metadata={"identifier": raw[:120]}, request=request
        )
        raise AuthenticationFailed("Invalid login or password.", code="invalid_credentials")

    has_platform = bool(platform_permissions_for(user))
    if platform_only and not has_platform:
        raise AuthenticationFailed(
            "This account is not a Super Admin.", code="not_platform_admin"
        )
    if not platform_only and has_platform:
        # Pure Super Admin accounts must use /superadmin/login.
        from apps.tenancy.models import MembershipStatus

        has_brand = user.memberships.filter(status=MembershipStatus.ACTIVE).exists()
        if not has_brand:
            raise AuthenticationFailed(
                "Use the Super Admin login page for this account.",
                code="use_superadmin_login",
            )
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


def _hash_otp(user_id, code: str) -> str:
    material = f"{settings.SECRET_KEY}:pwdreset:{user_id}:{code}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _is_brand_admin(user) -> bool:
    from apps.tenancy.models import MembershipStatus

    if user.email.endswith(STAFF_EMAIL_SUFFIX):
        return False
    return user.memberships.filter(is_owner=True, status=MembershipStatus.ACTIVE).exists()


def mask_email(email: str) -> str:
    """Mask middle characters: admin@brand.test → a***n@brand.test"""
    email = (email or "").strip()
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[:1] + "***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def get_brand_portal(slug: str) -> dict | None:
    """Public brand portal card: name + masked Brand Admin email."""
    from apps.tenancy.models import MembershipStatus, Organization, OrganizationStatus

    organization = Organization.objects.filter(slug=slug.strip().lower()).first()
    if organization is None or organization.status == OrganizationStatus.DEACTIVATED:
        return None
    owner = (
        organization.memberships.filter(is_owner=True, status=MembershipStatus.ACTIVE)
        .select_related("user")
        .first()
    )
    admin_email = owner.user.email if owner else (organization.contact_email or "")
    return {
        "name": organization.name,
        "slug": organization.slug,
        "masked_admin_email": mask_email(admin_email) if admin_email else "",
    }


def _brand_admin_for_slug(slug: str):
    from apps.tenancy.models import MembershipStatus, Organization, OrganizationStatus

    organization = Organization.objects.filter(slug=slug.strip().lower()).first()
    if organization is None or organization.status == OrganizationStatus.DEACTIVATED:
        return None, None
    membership = (
        organization.memberships.filter(is_owner=True, status=MembershipStatus.ACTIVE)
        .select_related("user")
        .first()
    )
    if membership is None or not membership.user.is_active:
        return organization, None
    return organization, membership.user


def _deliver_otp_email(*, email: str, code: str) -> None:
    """
    Deliver OTP using Django's mail backend.
    Default is console (no EMAIL_HOST / SMTP env required) — code prints in the server log.
    """
    send_system_email(
        subject="Your Zaylan password reset code",
        message=(
            f"Your password reset code is {code}.\n\n"
            f"It expires in {OTP_TTL_MINUTES} minutes. "
            "If you did not request this, you can ignore this email."
        ),
        recipients=[email],
        html_message=(
            f"<p>Your password reset code is <strong>{code}</strong>.</p>"
            f"<p>It expires in {OTP_TTL_MINUTES} minutes.</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        ),
    )


def request_password_reset(*, slug: str, request=None) -> None:
    """
    Send a 6-digit OTP to the Brand Admin for this brand slug.
    Always returns success to the client (no brand/account enumeration).
    """
    organization, user = _brand_admin_for_slug(slug)
    if user is None:
        record_event(
            action="auth.password_reset_requested",
            metadata={"slug": slug, "eligible": False},
            request=request,
        )
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    PasswordResetOTP.objects.filter(user=user, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    PasswordResetOTP.objects.create(
        user=user,
        code_hash=_hash_otp(user.pk, code),
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    _deliver_otp_email(email=user.email, code=code)
    record_event(
        action="auth.password_reset_requested",
        actor=user,
        metadata={"slug": organization.slug if organization else slug, "eligible": True},
        request=request,
    )


@transaction.atomic
def confirm_password_reset(*, slug: str, otp: str, new_password: str, request=None) -> None:
    code = (otp or "").strip()
    if not code.isdigit() or len(code) != 6:
        raise ValidationError({"otp": ["Enter the 6-digit code sent to the Brand Admin email."]})

    _organization, user = _brand_admin_for_slug(slug)
    if user is None:
        raise ValidationError({"otp": ["Invalid or expired code."]})

    challenge = (
        PasswordResetOTP.objects.filter(user=user, consumed_at__isnull=True)
        .order_by("-created_at")
        .select_for_update()
        .first()
    )
    if challenge is None or challenge.expires_at < timezone.now():
        raise ValidationError({"otp": ["Invalid or expired code."]})
    if challenge.attempts >= OTP_MAX_ATTEMPTS:
        raise ValidationError({"otp": ["Too many attempts. Request a new code."]})

    if not secrets.compare_digest(challenge.code_hash, _hash_otp(user.pk, code)):
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        raise ValidationError({"otp": ["Invalid or expired code."]})

    validate_password(new_password, user)
    user.set_password(new_password)
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password", "password_changed_at"])
    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at"])
    PasswordResetOTP.objects.filter(user=user, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    revoke_all_refresh_tokens(user)
    record_event(action="auth.password_reset_completed", actor=user, request=request)
