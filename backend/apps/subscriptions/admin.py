from django.contrib import admin

from .models import Feature, Plan, PlanEntitlement


class PlanEntitlementInline(admin.TabularInline):
    model = PlanEntitlement
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "trial_days")
    inlines = [PlanEntitlementInline]


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_limit")
    readonly_fields = ("code", "name", "description", "is_limit")
