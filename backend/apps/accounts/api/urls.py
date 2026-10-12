from django.urls import path

from apps.tenancy.api.views import InvitationAcceptView, InvitationLookupView

from .views import LoginView, LogoutView, PasswordChangeView, RefreshView

urlpatterns = [
    path("login", LoginView.as_view(), name="auth-login"),
    path("refresh", RefreshView.as_view(), name="auth-refresh"),
    path("logout", LogoutView.as_view(), name="auth-logout"),
    path("password/change", PasswordChangeView.as_view(), name="auth-password-change"),
    path("invitations/lookup", InvitationLookupView.as_view(), name="invitation-lookup"),
    path("invitations/accept", InvitationAcceptView.as_view(), name="invitation-accept"),
]
