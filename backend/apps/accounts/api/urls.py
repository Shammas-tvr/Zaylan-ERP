from django.urls import path

from apps.tenancy.api.views import InvitationAcceptView, InvitationLookupView

from .views import (
    BrandPortalView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordForgotView,
    PasswordResetView,
    RefreshView,
    SuperAdminLoginView,
)

urlpatterns = [
    path("login", LoginView.as_view(), name="auth-login"),
    path("superadmin/login", SuperAdminLoginView.as_view(), name="auth-superadmin-login"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("password/change", PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/forgot", PasswordForgotView.as_view(), name="auth-password-forgot"),
    path("password/reset", PasswordResetView.as_view(), name="auth-password-reset"),
    path("brands/<slug:slug>/portal", BrandPortalView.as_view(), name="auth-brand-portal"),
    path("invitations/lookup", InvitationLookupView.as_view(), name="invitation-lookup"),
    path("invitations/accept", InvitationAcceptView.as_view(), name="invitation-accept"),
]
