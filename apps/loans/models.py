from django.db import models
from django.utils import timezone
from apps.groups.models import Group, GroupMember
from apps.accounts.models import User
import uuid

class Loan(models.Model):
    LOAN_TYPES = [
        ('group_loan', 'Group Loan'),
        ('ecoret_loan', 'ECORET Loan'),
    ]
    
    LOAN_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('declined', 'Declined'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='loans')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_payable = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.IntegerField()
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=LOAN_STATUS, default='pending', db_index=True)
    request_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, 
        related_name='loans_created'
    )
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='loans_approved'
    )
    notes = models.TextField(blank=True)
    attachment = models.FileField(upload_to='loan_attachments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loans'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.member.full_name} - {self.amount}'
    
    def get_balance(self):
        total_paid = self.repayments.aggregate(total=models.Sum('amount'))['total'] or 0
        return self.total_payable - total_paid
    
    def is_completed(self):
        return self.get_balance() <= 0
    
    def approve(self, user):
        if self.status == 'pending':
            self.status = 'approved'
            self.approval_date = timezone.now()
            self.approved_by = user
            self.save()
            return True
        return False
    
    def activate(self):
        if self.status == 'approved':
            self.status = 'active'
            self.save()
            return True
        return False

class LoanRepayment(models.Model):
    PAYMENT_METHODS = [
        ('mpamba', 'Mpamba'),
        ('airtel_money', 'Airtel Money'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    principal_paid = models.DecimalField(max_digits=10, decimal_places=2)
    interest_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'loan_repayments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f'{self.loan.member.full_name} - {self.amount}'

class LoanRequest(models.Model):
    """Requests to ECORET for loans"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('reviewing', 'Under Review'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='loan_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    request_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    attachments = models.JSONField(default=list)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loan_requests'
        ordering = ['-request_date']
    
    def __str__(self):
        return f'{self.group.group_name} - {self.amount}'
    
    def approve(self, user):
        self.status = 'approved'
        self.approval_date = timezone.now()
        self.save()
    
    def decline(self, user):
        self.status = 'declined'
        self.save()


# ✅ UPDATED: Group Loan Settings with separate rates for each loan type
class LoanSettings(models.Model):
    """Group loan settings with dynamic interest rates"""
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='loan_settings')
    
    # ===== GROUP LOAN SETTINGS (Set by Group Chairman) =====
    group_loan_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=10.00,
        help_text="Interest rate (%) for group loans. Set by group chairman."
    )
    
    group_loan_duration_months = models.IntegerField(
        default=6,
        help_text="Repayment duration in months for group loans. Set by group chairman."
    )
    
    group_loan_max_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=500000,
        help_text="Maximum group loan amount. Set by group chairman."
    )
    
    group_loan_min_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=1000,
        help_text="Minimum group loan amount. Set by group chairman."
    )
    
    # ===== ECORET LOAN SETTINGS (Set by ECORET Admin) =====
    ecoret_loan_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=5.00,
        help_text="Interest rate (%) for ECORET loans. Set by ECORET admin."
    )
    
    ecoret_loan_duration_months = models.IntegerField(
        default=12,
        help_text="Repayment duration in months for ECORET loans. Set by ECORET admin."
    )
    
    ecoret_loan_max_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=1000000,
        help_text="Maximum ECORET loan amount. Set by ECORET admin."
    )
    
    ecoret_loan_min_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=10000,
        help_text="Minimum ECORET loan amount. Set by ECORET admin."
    )
    
    # ===== GENERAL SETTINGS =====
    requires_guarantor = models.BooleanField(
        default=True,
        help_text="Does this group require a guarantor for loans?"
    )
    
    min_guarantors = models.IntegerField(
        default=2,
        help_text="Minimum number of guarantors required for loans."
    )
    
    grace_period_days = models.IntegerField(
        default=7,
        help_text="Days after due date before late fees apply."
    )
    
    late_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=0,
        help_text="Late fee as percentage of overdue amount."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'loan_settings'
    
    def __str__(self):
        return f'Loan Settings - {self.group.group_name}'


# ✅ NEW: ECORET Global Settings
class ECORETSettings(models.Model):
    """
    Global settings for ECORET.
    Only one instance should exist in the database.
    """
    
    # ===== ECORET LOAN RATES =====
    ecoret_loan_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=5.00,
        help_text="Current ECORET loan interest rate (%)"
    )
    
    ecoret_loan_duration_months = models.IntegerField(
        default=12,
        help_text="ECORET loan duration in months"
    )
    
    ecoret_loan_max_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=1000000,
        help_text="Maximum ECORET loan amount"
    )
    
    ecoret_loan_min_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=10000,
        help_text="Minimum ECORET loan amount"
    )
    
    # ===== ECORET SERVICE FEES =====
    service_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=2.5,
        help_text="ECORET service fee (%) per transaction"
    )
    
    # ===== AUDIT =====
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text="Admin who last updated these settings"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ecoret_settings'
        verbose_name_plural = "ECORET Settings"
    
    def __str__(self):
        return "ECORET Loan Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and ECORETSettings.objects.exists():
            raise Exception("ECORET settings already exist. Only one instance allowed.")
        super().save(*args, **kwargs)