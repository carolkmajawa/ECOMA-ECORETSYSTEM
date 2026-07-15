from django.db import models
from apps.groups.models import Group, GroupMember
from apps.accounts.models import User
import uuid

class USSDRequest(models.Model):
    """Log USSD requests"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, db_index=True)
    session_id = models.CharField(max_length=255, db_index=True)
    service_code = models.CharField(max_length=20)
    request_text = models.TextField(blank=True)
    response_text = models.TextField(blank=True)
    group_code = models.CharField(max_length=20, null=True, blank=True)
    group_member = models.ForeignKey(GroupMember, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ussd_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.phone_number} - {self.session_id}"

class USSDSession(models.Model):
    """Track USSD sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, db_index=True)
    group_code = models.CharField(max_length=20, null=True, blank=True)
    group_id = models.UUIDField(null=True, blank=True)
    member_id = models.UUIDField(null=True, blank=True)
    language = models.CharField(max_length=2, default='en')
    current_menu = models.CharField(max_length=50, default='welcome')
    loan_type = models.CharField(max_length=20, null=True, blank=True)
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ussd_sessions'
    
    def __str__(self):
        return f"{self.phone_number} - {self.session_id}"

class USSDOTP(models.Model):
    """Store USSD OTPs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, db_index=True)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50, choices=[
        ('loan_approval', 'Loan Approval'),
        ('member_verification', 'Member Verification'),
        ('transaction', 'Transaction')
    ])
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    correlation_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ussd_otps'
    
    def __str__(self):
        return f"{self.phone_number} - {self.otp_code}"

class USSDLoanRequest(models.Model):
    """Track loan requests from USSD"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    loan_type = models.CharField(max_length=20, default='group_loan')
    status = models.CharField(max_length=20, choices=[
        ('pending_otp', 'Pending OTP'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('declined', 'Declined')
    ], default='pending_otp')
    otp_session_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ussd_loan_requests'
    
    def __str__(self):
        return f"{self.member.full_name} - MK{self.amount}"