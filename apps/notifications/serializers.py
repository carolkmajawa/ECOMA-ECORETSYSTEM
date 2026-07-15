from rest_framework import serializers
from .models import Notification, NotificationPreference

class NotificationSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.group_name', read_only=True, allow_null=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'user_name', 'group', 'group_name',
            'title', 'message', 'notification_type', 'is_read',
            'read_at', 'data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'read_at']

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'loan_alerts', 'due_reminders', 'funding_alerts',
            'group_notices', 'attendance_reminders', 'email_notifications',
            'sms_notifications', 'push_notifications'
        ]