from rest_framework import serializers

from .models import NotificationPreference, NotificationLog, NotificationCategory, DEFAULT_FREQUENCY_BY_ROLE


class NotificationPreferenceItemSerializer(serializers.Serializer):
    """
    One row per category for the CURRENT user — always returns every
    category (even ones with no DB override yet, filled in from the
    role default), so the frontend never has to special-case "missing".
    """
    category = serializers.CharField()
    category_label = serializers.CharField()
    frequency = serializers.CharField()
    is_default = serializers.BooleanField()


class NotificationPreferenceUpdateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=NotificationCategory.choices)
    frequency = serializers.ChoiceField(choices=['immediate', 'digest', 'off'])


class NotificationLogSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = NotificationLog
        fields = [
            'id', 'category', 'category_label', 'subject', 'summary',
            'related_object_type', 'related_object_id',
            'status', 'sent_at', 'read_at',
        ]
