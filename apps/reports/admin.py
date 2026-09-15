# apps/reports/admin.py

from django.contrib import admin
from .models import Report

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'group', 'report_type', 'status', 'format', 'created_at', 'is_ready']
    list_filter = ['status', 'report_type', 'format']
    search_fields = ['group__group_name', 'generated_by__email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Report Information', {
            'fields': ('id', 'group', 'cycle', 'report_type', 'format', 'status')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
        ('Filters', {
            'fields': ('include_members', 'include_sections')
        }),
        ('Files', {
            'fields': ('pdf_file', 'excel_file')
        }),
        ('Data', {
            'fields': ('report_data',)
        }),
        ('Metadata', {
            'fields': ('generated_by', 'file_size', 'download_count', 'created_at', 'updated_at', 'completed_at')
        }),
    )