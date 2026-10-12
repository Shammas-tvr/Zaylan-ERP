from django.urls import path

from apps.tenancy.api.views import MyContextView, MyOrganizationsView, MyPermissionsView

from .views import MeView

urlpatterns = [
    path("", MeView.as_view(), name="me"),
    path("organizations", MyOrganizationsView.as_view(), name="me-organizations"),
    path("context", MyContextView.as_view(), name="me-context"),
    path("permissions", MyPermissionsView.as_view(), name="me-permissions"),
]
