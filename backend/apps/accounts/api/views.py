from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from apps.audit_logs.services import record_event

from .. import services
from .serializers import (
    AccessTokenSerializer,
    BrandPortalSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordForgotSerializer,
    PasswordResetSerializer,
    ProfileUpdateSerializer,
    SessionSerializer,
)


class PublicAuthView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]

    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'


def _require_trusted_origin(request) -> None:
    if not services.is_trusted_origin(request):
        raise PermissionDenied("Request origin is not allowed.")


class LoginView(PublicAuthView):
    throttle_scope = "auth_login"
    platform_only = False

    @extend_schema(request=LoginSerializer, responses=SessionSerializer)
    def post(self, request):
        _require_trusted_origin(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.authenticate_credentials(
            request,
            identifier=serializer.validated_data["identifier"],
            password=serializer.validated_data["password"],
            platform_only=self.platform_only,
        )
        access, refresh = services.issue_tokens(user)
        record_event(action="auth.login", actor=user, request=request)
        response = Response({"access": access, "user": MeSerializer(user).data})
        services.set_refresh_cookie(response, refresh)
        return response


class SuperAdminLoginView(LoginView):
    """Separate Super Admin login endpoint used by /superadmin/login."""

    platform_only = True


class RefreshView(PublicAuthView):
    throttle_scope = "auth_refresh"

    @extend_schema(request=None, responses=SessionSerializer)
    def post(self, request):
        _require_trusted_origin(request)
        try:
            access, refresh, user = services.rotate_refresh_token(
                services.read_refresh_cookie(request), request=request
            )
        except AuthenticationFailed as exc:
            response = Response(
                {"error": {"code": exc.get_codes(), "message": str(exc.detail)}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            services.clear_refresh_cookie(response)
            return response
        response = Response({"access": access, "user": MeSerializer(user).data})
        services.set_refresh_cookie(response, refresh)
        return response


class LogoutView(PublicAuthView):
    throttle_scope = "auth_refresh"

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        _require_trusted_origin(request)
        services.revoke_refresh_token(services.read_refresh_cookie(request))
        response = Response(status=status.HTTP_204_NO_CONTENT)
        services.clear_refresh_cookie(response)
        return response


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses=AccessTokenSerializer)
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_password(request.user, **serializer.validated_data, request=request)
        request.user.refresh_from_db()
        access, refresh = services.issue_tokens(request.user)
        response = Response({"access": access})
        services.set_refresh_cookie(response, refresh)
        return response


class BrandPortalView(PublicAuthView):
    """Public brand card for /b/{slug}/login — name + masked Brand Admin email."""

    throttle_scope = "auth_login"

    @extend_schema(responses=BrandPortalSerializer)
    def get(self, request, slug: str):
        portal = services.get_brand_portal(slug)
        if portal is None:
            return Response(
                {"error": {"code": "not_found", "message": "Brand not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(BrandPortalSerializer(portal).data)


class PasswordForgotView(PublicAuthView):
    """Send OTP to this brand's Brand Admin (resolved from slug). No email input."""

    throttle_scope = "auth_password_reset"

    @extend_schema(request=PasswordForgotSerializer, responses={200: None})
    def post(self, request):
        _require_trusted_origin(request)
        serializer = PasswordForgotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(slug=serializer.validated_data["slug"], request=request)
        return Response(
            {
                "detail": "If this brand has a Brand Admin, a one-time code was sent to their email.",
            }
        )


class PasswordResetView(PublicAuthView):
    """Confirm OTP and set a new Brand Admin password for this brand slug."""

    throttle_scope = "auth_password_reset"

    @extend_schema(request=PasswordResetSerializer, responses={200: None})
    def post(self, request):
        _require_trusted_origin(request)
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.confirm_password_reset(
            slug=serializer.validated_data["slug"],
            otp=serializer.validated_data["otp"],
            new_password=serializer.validated_data["new_password"],
            request=request,
        )
        return Response({"detail": "Password updated. You can sign in now."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses=MeSerializer)
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.full_name = serializer.validated_data["full_name"]
        request.user.save(update_fields=["full_name"])
        return Response(MeSerializer(request.user).data)
