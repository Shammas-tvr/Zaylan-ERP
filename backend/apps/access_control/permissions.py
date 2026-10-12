"""DRF permission classes. Every rule fails closed: an action without a declared rule is denied."""

from rest_framework.permissions import BasePermission

from apps.core.exceptions import FeatureNotAvailable

from .services import platform_permissions_for


def _action(request, view) -> str:
    return getattr(view, "action", None) or request.method.lower()


class TenantPermission(BasePermission):
    """
    Views declare ``permission_rules = {action: "resource.action" | None}``.

    ``None`` explicitly allows any member. Actions listed in ``branch_scoped_actions`` pass the
    view-level check when the permission is held in any branch; objects are then checked against
    their own branch via ``get_permission_branch_id``.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        ctx = getattr(request, "tenant", None)
        if ctx is None:
            return False
        action = _action(request, view)
        rules = getattr(view, "permission_rules", {})
        if action not in rules:
            return False

        feature = getattr(view, "feature_rules", {}).get(action) or getattr(
            view, "required_feature", None
        )
        if feature and not ctx.feature_enabled(feature):
            raise FeatureNotAvailable()

        code = rules[action]
        if code is None:
            return True
        if action in getattr(view, "branch_scoped_actions", ()):
            return ctx.has_permission_anywhere(code)
        return ctx.has_permission(code)

    def has_object_permission(self, request, view, obj) -> bool:
        ctx = request.tenant
        action = _action(request, view)
        code = getattr(view, "permission_rules", {}).get(action)
        if code is None:
            return True
        if action in getattr(view, "branch_scoped_actions", ()):
            get_branch_id = getattr(view, "get_permission_branch_id", None)
            if get_branch_id is None:
                # The view's queryset is already restricted to permitted branches.
                return True
            return ctx.has_permission(code, get_branch_id(obj))
        return ctx.has_permission(code)


class PlatformPermission(BasePermission):
    """Views declare ``platform_rules = {action: "platform.*"}``; undeclared actions are denied."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        code = getattr(view, "platform_rules", {}).get(_action(request, view))
        if code is None:
            return False
        return code in platform_permissions_for(request.user)
