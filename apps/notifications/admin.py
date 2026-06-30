from django.contrib import admin
from .models import Notification, NotificationPreference, NotificationQueue

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read']
    search_fields = ['title', 'message', 'user__email']

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'loan_alerts', 'due_reminders', 'push_notifications']

@admin.register(NotificationQueue)
class NotificationQueueAdmin(admin.ModelAdmin):
    list_display = ['notification', 'status', 'channel', 'attempt_count', 'created_at']
    list_filter = ['status', 'channel']