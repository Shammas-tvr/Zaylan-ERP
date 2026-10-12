from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Lifecycle metadata only. Tenant business data is never registered in Django admin."""

    list_display = ("name", "slug", "industry", "status", "onboarding_status", "created_at")
    list_filter = ("status", "industry", "onboarding_status")
    search_fields = ("name", "slug")
    readonly_fields = [field.name for field in Organization._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
