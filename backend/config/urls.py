from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1 = [
    path("auth/", include("apps.accounts.api.urls")),
    path("me/", include("apps.accounts.api.me_urls")),
    path("organization/", include("apps.tenancy.api.urls")),
    path("organization/", include("apps.access_control.api.urls")),
    path("branches/", include("apps.branches.api.urls")),
    path("audit-events/", include("apps.audit_logs.api.urls")),
    path("platform/", include("apps.platform_admin.api.urls")),
    path("expenses/", include("apps.expenses.api.urls")),
    path("notifications/", include("apps.notifications.api.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]

if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
