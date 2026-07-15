from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.groups.models import Group
import uuid

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('loan_approval', 'Loan Approval'),
        ('loan_due', 'Loan Due'),
        ('funding', 'Funding Alert'),
        ('group_notice', 'Group Notice'),
        ('loan_request', 'Loan Request'),
        ('payment_received', 'Payment Received'),
        ('attendance', 'Attendance Reminder'),
        ('system', 'System Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True, 
                             related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.title} - {self.user.email}'
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    loan_alerts = models.BooleanField(default=True)
    due_reminders = models.BooleanField(default=True)
    funding_alerts = models.BooleanField(default=True)
    group_notices = models.BooleanField(default=True)
    attendance_reminders = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
    
    def __str__(self):
        return f'Preferences - {self.user.email}'

class NotificationQueue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, 
                                    related_name='queue_items')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ], default='pending')
    channel = models.CharField(max_length=20, choices=[
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification')
    ])
    attempt_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notification_queue'
        ordering = ['created_at']