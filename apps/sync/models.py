from django.db import models
from django.utils import timezone
from apps.accounts.models import User
import uuid

class DeviceSync(models.Model):
    """Track sync status for each device"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sync_devices')
    device_id = models.CharField(max_length=255, db_index=True)
    device_name = models.CharField(max_length=255, blank=True)
    last_sync_at = models.DateTimeField(default=timezone.now)
    last_sync_success = models.BooleanField(default=True)
    sync_error = models.TextField(blank=True)
    
    total_syncs = models.IntegerField(default=0)
    failed_syncs = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'device_sync'
        unique_together = ['user', 'device_id']
    
    def __str__(self):
        return f"{self.user.email} - {self.device_id}"

class SyncLog(models.Model):
    """Log all sync operations"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sync_logs')
    device = models.ForeignKey(DeviceSync, on_delete=models.CASCADE, null=True, blank=True)
    
    action = models.CharField(max_length=20, choices=[
        ('upload', 'Upload'),
        ('download', 'Download'),
        ('conflict', 'Conflict Resolved'),
        ('error', 'Error'),
    ])
    
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100, blank=True)
    
    data_sent = models.JSONField(default=dict, blank=True)
    data_received = models.JSONField(default=dict, blank=True)
    
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('partial', 'Partial'),
    ])
    
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sync_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.created_at}"