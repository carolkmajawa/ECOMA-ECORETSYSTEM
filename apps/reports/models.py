import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Report(models.Model):
    """Model to store generated reports"""
    
    REPORT_TYPES = [
        ('cycle_summary', 'Cycle Summary'),
        ('member_performance', 'Member Performance'),
        ('financial', 'Financial Report'),
        ('full_cycle', 'Full Cycle Report'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('both', 'Both'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES, default='full_cycle')
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='pdf')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='generated_reports')
    
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    cycle_start_date = models.DateTimeField(null=True, blank=True)
    cycle_end_date = models.DateTimeField(null=True, blank=True)
    is_cycle_active = models.BooleanField(default=False)
    
    include_members = models.JSONField(default=list, help_text="List of member IDs to include")
    include_sections = models.JSONField(default=list, help_text="List of sections to include")
    
    pdf_file = models.FileField(upload_to='reports/pdfs/', null=True, blank=True)
    excel_file = models.FileField(upload_to='reports/excel/', null=True, blank=True)
    
    report_data = models.JSONField(default=dict)
    
    file_size = models.IntegerField(default=0)
    download_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'reports'
        ordering = ['-created_at']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
    
    def __str__(self):
        return f"{self.group.group_name} - {self.report_type} - {self.created_at.date()}"
    
    @property
    def is_ready(self):
        return self.status == 'completed' and self.pdf_file and self.pdf_file.name
    
    @property
    def file_exists(self):
        if self.format == 'pdf':
            return bool(self.pdf_file and self.pdf_file.name)
        elif self.format == 'excel':
            return bool(self.excel_file and self.excel_file.name)
        else:
            return bool(self.pdf_file and self.pdf_file.name) or bool(self.excel_file and self.excel_file.name)
    
    def get_file(self):
        if self.format == 'pdf':
            return self.pdf_file
        elif self.format == 'excel':
            return self.excel_file
        else:
            return self.pdf_file


    def delete(self, using=None, keep_parents=False):
        """Delete the report and its associated files"""
    # Delete the PDF file
        if self.pdf_file:
            try:
                self.pdf_file.delete(save=False)
            except:
                pass
    
    # Delete the Excel file
        if self.excel_file:
            try:
                self.excel_file.delete(save=False)
            except:
                pass
    
    # Delete the report record
        super().delete(using=using, keep_parents=keep_parents)