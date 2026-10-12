from rest_framework import serializers

from ..models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    branch_code = serializers.CharField(source="branch.code", default=None, read_only=True)

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "occurred_at",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "branch_code",
            "request_id",
            "metadata",
        )
        read_only_fields = fields
