from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.audit_logs.services import record_event
from apps.core.exceptions import BusinessRuleViolation

from ..models import MembershipStatus, OrganizationMembership


@transaction.atomic
def change_membership_status(ctx, membership, status: str, *, request=None):
    membership = OrganizationMembership.objects.select_for_update().get(
        pk=membership.pk, organization=ctx.organization
    )
    if membership.pk == ctx.membership.pk:
        raise PermissionDenied("You cannot change your own membership status.")
    if membership.is_owner:
        raise BusinessRuleViolation("The organization owner cannot be suspended.")
    if status not in MembershipStatus.values:
        raise BusinessRuleViolation("Unknown membership status.")
    if membership.status == status:
        return membership
    if status == MembershipStatus.ACTIVE:
        from apps.subscriptions.services import enforce_limit

        active = ctx.organization.memberships.filter(status=MembershipStatus.ACTIVE).count()
        enforce_limit(ctx.entitlements, "members", active)
    previous = membership.status
    membership.status = status
    membership.save(update_fields=["status", "updated_at"])
    record_event(
        action="members.status_changed",
        actor=ctx.user,
        organization=ctx.organization,
        target=membership,
        metadata={"email": membership.user.email, "from": previous, "to": status},
        request=request,
    )
    return membership
