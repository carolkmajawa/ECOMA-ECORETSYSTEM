# apps/reports/serializers.py

from rest_framework import serializers
from .models import Report
from apps.groups.models import Group

class ReportSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True)
    pdf_file_url = serializers.SerializerMethodField()
    excel_file_url = serializers.SerializerMethodField()
    is_ready = serializers.SerializerMethodField()
    file_exists = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            'id', 'group', 'group_name', 'report_type', 'format',
            'status', 'generated_by', 'generated_by_name', 'start_date',
            'end_date', 'cycle_start_date', 'cycle_end_date', 'is_cycle_active',
            'include_members', 'include_sections', 'pdf_file', 'pdf_file_url',
            'excel_file', 'excel_file_url', 'report_data', 'file_size', 
            'download_count', 'created_at', 'updated_at', 'completed_at', 
            'is_ready', 'file_exists'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'completed_at',
            'generated_by', 'file_size', 'download_count'
        ]
    
    def get_pdf_file_url(self, obj):
        """Get PDF file URL"""
        if obj.pdf_file and hasattr(obj.pdf_file, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_file.url)
            return obj.pdf_file.url
        return None
    
    def get_excel_file_url(self, obj):
        """Get Excel file URL"""
        if obj.excel_file and hasattr(obj.excel_file, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.excel_file.url)
            return obj.excel_file.url
        return None
    
    def get_is_ready(self, obj):
        """Check if report is ready"""
        return obj.status == 'completed' and bool(obj.pdf_file)
    
    def get_file_exists(self, obj):
        """Check if file exists"""
        if obj.format == 'pdf':
            return bool(obj.pdf_file)
        elif obj.format == 'excel':
            return bool(obj.excel_file)
        else:
            return bool(obj.pdf_file) or bool(obj.excel_file)


class ReportGenerateSerializer(serializers.Serializer):
    group_id = serializers.UUIDField(required=True)
    period = serializers.ChoiceField(
        choices=['this_cycle', 'last_cycle', 'this_month', 'last_month', 'custom', 'all_time'],
        required=True
    )
    start_date = serializers.DateTimeField(required=False, allow_null=True)
    end_date = serializers.DateTimeField(required=False, allow_null=True)
    include_members = serializers.ListField(
        child=serializers.UUIDField(), 
        required=False, 
        default=list
    )
    include_sections = serializers.ListField(
        child=serializers.CharField(), 
        required=False, 
        default=list
    )
    format = serializers.ChoiceField(
        choices=['pdf', 'excel', 'both'], 
        default='pdf'
    )
    
    def validate(self, data):
        period = data.get('period')
        
        if period == 'custom':
            if not data.get('start_date'):
                raise serializers.ValidationError({
                    'start_date': 'Start date is required for custom period'
                })
            if not data.get('end_date'):
                raise serializers.ValidationError({
                    'end_date': 'End date is required for custom period'
                })
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'start_date': 'Start date must be before end date'
                })
        
        return data
    
    def validate_group_id(self, value):
        try:
            group = Group.objects.get(id=value)
        except Group.DoesNotExist:
            raise serializers.ValidationError('Group not found')
        return value