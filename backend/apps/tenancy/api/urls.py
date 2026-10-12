from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    BrandingView,
    InvitationViewSet,
    MemberViewSet,
    OrganizationView,
    SubscriptionView,
)

router = SimpleRouter(trailing_slash=False)
router.register("members", MemberViewSet, basename="member")
router.register("invitations", InvitationViewSet, basename="invitation")

urlpatterns = [
    path("", OrganizationView.as_view(), name="organization"),
    path("branding", BrandingView.as_view(), name="organization-branding"),
    path("subscription", SubscriptionView.as_view(), name="organization-subscription"),
    *router.urls,
]
