import django_filters

from ..models import AuditEvent


class AuditEventFilter(django_filters.FilterSet):
    action = django_filters.CharFilter(field_name="action", lookup_expr="startswith")
    actor_email = django_filters.CharFilter(field_name="actor_email", lookup_expr="iexact")
    target_type = django_filters.CharFilter()
    occurred_after = django_filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_before = django_filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="lt")

    class Meta:
        model = AuditEvent
        fields = ("action", "actor_email", "target_type", "occurred_after", "occurred_before")
