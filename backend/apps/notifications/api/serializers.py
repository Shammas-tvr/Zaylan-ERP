from rest_framework import serializers

from apps.notifications.models import BrandNotificationSettings, Notification


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "title",
            "body",
            "link_path",
            "expense_id",
            "is_read",
            "read_at",
            "created_at",
        )
        read_only_fields = fields


class BrandNotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandNotificationSettings
        fields = (
            "primary_email",
            "extra_recipient_emails",
            "reminder_intervals_hours",
            "reminders_enabled",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class BrandNotificationSettingsWriteSerializer(serializers.Serializer):
    primary_email = serializers.EmailField(required=False, allow_blank=True)
    extra_recipient_emails = serializers.ListField(
        child=serializers.EmailField(), required=False, max_length=20
    )
    reminder_intervals_hours = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=720), required=False, max_length=10
    )
    reminders_enabled = serializers.BooleanField(required=False)


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()
