from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation, FeatureNotAvailable, PlanLimitReached

from .catalog import DEFAULT_PLANS, FEATURES
from .models import Feature, OrganizationSubscription, Plan, PlanEntitlement, SubscriptionStatus

ACCESS_STATUSES = frozenset(
    {SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE}
)


@dataclass(frozen=True)
class Entitlement:
    enabled: bool
    limit: int | None = None


def sync_feature_catalog() -> None:
    for feature in FEATURES:
        Feature.objects.update_or_create(
            code=feature.code,
            defaults={
                "name": feature.name,
                "description": feature.description,
                "is_limit": feature.is_limit,
            },
        )


def sync_feature_catalog_on_migrate(**kwargs) -> None:
    sync_feature_catalog()


@transaction.atomic
def ensure_default_plans() -> None:
    sync_feature_catalog()
    features = {f.code: f for f in Feature.objects.all()}
    for code, spec in DEFAULT_PLANS.items():
        plan, created = Plan.objects.get_or_create(
            code=code, defaults={"name": spec["name"], "trial_days": spec["trial_days"]}
        )
        if not created:
            continue
        for feature_code, value in spec["entitlements"].items():
            feature = features[feature_code]
            PlanEntitlement.objects.create(
                plan=plan,
                feature=feature,
                enabled=True,
                limit_value=value if feature.is_limit else None,
            )


def subscription_allows_access(subscription: OrganizationSubscription | None, now=None) -> bool:
    if subscription is None or subscription.status not in ACCESS_STATUSES:
        return False
    if subscription.status == SubscriptionStatus.TRIALING:
        return subscription.trial_ends_at is not None and subscription.trial_ends_at > (
            now or timezone.now()
        )
    return True


def get_entitlements(subscription: OrganizationSubscription | None) -> dict[str, Entitlement]:
    entitlements = {feature.code: Entitlement(enabled=False) for feature in FEATURES}
    if subscription is None:
        return entitlements
    for row in PlanEntitlement.objects.filter(plan_id=subscription.plan_id).select_related(
        "feature"
    ):
        entitlements[row.feature.code] = Entitlement(
            enabled=row.enabled, limit=row.limit_value if row.feature.is_limit else None
        )
    return entitlements


def require_feature(entitlements: dict[str, Entitlement], code: str) -> None:
    if not entitlements.get(code, Entitlement(enabled=False)).enabled:
        raise FeatureNotAvailable()


def enforce_limit(entitlements: dict[str, Entitlement], code: str, current_count: int) -> None:
    entitlement = entitlements.get(code, Entitlement(enabled=False))
    if not entitlement.enabled:
        raise FeatureNotAvailable()
    if entitlement.limit is not None and current_count >= entitlement.limit:
        raise PlanLimitReached(f"The plan allows at most {entitlement.limit} {code}.")


def start_subscription(organization, plan: Plan) -> OrganizationSubscription:
    if not plan.is_active:
        raise BusinessRuleViolation("This plan is not available.")
    if plan.trial_days:
        status = SubscriptionStatus.TRIALING
        trial_ends_at = timezone.now() + timedelta(days=plan.trial_days)
    else:
        status = SubscriptionStatus.ACTIVE
        trial_ends_at = None
    return OrganizationSubscription.objects.create(
        organization=organization, plan=plan, status=status, trial_ends_at=trial_ends_at
    )


@transaction.atomic
def change_subscription(
    *,
    actor,
    subscription: OrganizationSubscription,
    plan: Plan | None = None,
    status: str | None = None,
    trial_ends_at: datetime | None = None,
    request=None,
) -> OrganizationSubscription:
    subscription = OrganizationSubscription.objects.select_for_update().get(pk=subscription.pk)
    changes = {}
    if plan is not None and plan.pk != subscription.plan_id:
        if not plan.is_active:
            raise BusinessRuleViolation("This plan is not available.")
        changes["plan"] = [subscription.plan.code, plan.code]
        subscription.plan = plan
    if status is not None and status != subscription.status:
        changes["status"] = [subscription.status, status]
        subscription.status = status
    if trial_ends_at is not None:
        changes["trial_ends_at"] = [
            subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
            trial_ends_at.isoformat(),
        ]
        subscription.trial_ends_at = trial_ends_at
    if subscription.status == SubscriptionStatus.TRIALING and subscription.trial_ends_at is None:
        raise BusinessRuleViolation("A trialing subscription needs a trial end date.")
    subscription.save()
    record_event(
        action="platform.subscription_changed",
        actor=actor,
        organization=subscription.organization,
        target=subscription,
        metadata=changes,
        request=request,
    )
    return subscription


def organization_usage(organization) -> dict[str, int]:
    from apps.tenancy.models import InvitationStatus, MembershipStatus

    return {
        "branches": organization.branches.count(),
        "members": organization.memberships.filter(status=MembershipStatus.ACTIVE).count(),
        "pending_invitations": organization.invitations.filter(
            status=InvitationStatus.PENDING, expires_at__gt=timezone.now()
        ).count(),
    }
