# apps/notifications/serializers.py
from rest_framework import serializers
from .models import Notification, NotificationPreference, NotificationQueue

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'group', 'title', 'message', 'notification_type',
            'is_read', 'read_at', 'data', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at']

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user', 'loan_alerts', 'due_reminders', 'funding_alerts',
            'group_notices', 'attendance_reminders', 'email_notifications',
            'sms_notifications', 'push_notifications', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

class NotificationQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationQueue
        fields = [
            'id', 'notification', 'status', 'channel', 'attempt_count',
            'error_message', 'created_at', 'sent_at'
        ]
        read_only_fields = ['id', 'created_at']