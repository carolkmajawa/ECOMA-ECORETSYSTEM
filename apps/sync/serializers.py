from rest_framework import serializers
from .models import DeviceSync, SyncLog

class DeviceSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceSync
        fields = [
            'id', 'user', 'device_id', 'device_name',
            'last_sync_at', 'last_sync_success', 'total_syncs',
            'failed_syncs', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class SyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncLog
        fields = [
            'id', 'user', 'device', 'action', 'entity_type',
            'entity_id', 'data_sent', 'data_received', 'status',
            'error_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']