from typing import Any

from apps.core.request_context import get_request_id

from .models import AuditEvent

_SENSITIVE_KEY_PARTS = ("password", "token", "secret", "authorization", "cookie")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if any(part in str(key).lower() for part in _SENSITIVE_KEY_PARTS)
            else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _client_ip(request) -> str | None:
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR") or None


def record_event(
    *,
    action: str,
    actor=None,
    organization=None,
    branch=None,
    target=None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict | None = None,
    request=None,
) -> AuditEvent:
    if target is not None:
        target_type = target_type or target._meta.label_lower
        target_id = target_id or str(target.pk)
    actor = actor if getattr(actor, "is_authenticated", False) else None
    return AuditEvent.objects.create(
        action=action,
        actor=actor,
        actor_email=actor.email if actor else "",
        organization=organization,
        branch=branch,
        target_type=target_type,
        target_id=str(target_id),
        request_id=get_request_id() or "",
        ip_address=_client_ip(request),
        metadata=_redact(metadata or {}),
    )
