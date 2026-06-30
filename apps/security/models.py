from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.groups.models import Group, GroupMember
import uuid

class TransactionAudit(models.Model):
    """Audit log for all financial transactions"""
    
    TRANSACTION_TYPES = [
        ('loan_creation', 'Loan Creation'),
        ('loan_approval', 'Loan Approval'),
        ('loan_disbursement', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
        ('savings_deposit', 'Savings Deposit'),
        ('savings_withdrawal', 'Savings Withdrawal'),
        ('mobile_money_payout', 'Mobile Money Payout'),
        ('mobile_money_collection', 'Mobile Money Collection'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True)
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, null=True)
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='pending')  # pending, success, failed
    error_message = models.TextField(blank=True)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'transaction_audits'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - MK{self.amount} - {self.status}"

class MobileMoneyTransaction(models.Model):
    """Track mobile money transactions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=20)  # payout, collection
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    provider = models.CharField(max_length=20)  # mpamba, airtel_money
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    response_data = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mobile_money_transactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} - {self.status}"