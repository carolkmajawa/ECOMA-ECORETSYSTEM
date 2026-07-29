# from django.db import models
# from django.utils import timezone
# from apps.groups.models import Group, GroupMember
# from apps.accounts.models import User
# import uuid

# class Loan(models.Model):
#     LOAN_TYPES = [
#         ('group_loan', 'Group Loan'),
#         ('ecoret_loan', 'ECORET Loan'),
#     ]
    
#     LOAN_STATUS = [
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('active', 'Active'),
#         ('completed', 'Completed'),
#         ('defaulted', 'Defaulted'),
#         ('declined', 'Declined'),
#     ]
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='loans')
#     member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='loans')
#     loan_type = models.CharField(max_length=20, choices=LOAN_TYPES)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
#     total_payable = models.DecimalField(max_digits=10, decimal_places=2)
#     duration_months = models.IntegerField()
#     purpose = models.TextField()
#     status = models.CharField(max_length=20, choices=LOAN_STATUS, default='pending', db_index=True)
#     request_date = models.DateTimeField(auto_now_add=True)
#     approval_date = models.DateTimeField(null=True, blank=True)
#     due_date = models.DateTimeField(null=True, blank=True)
#     created_by = models.ForeignKey(
#         User, on_delete=models.SET_NULL, null=True, 
#         related_name='loans_created'
#     )
#     approved_by = models.ForeignKey(
#         User, on_delete=models.SET_NULL, null=True,
#         related_name='loans_approved'
#     )
#     notes = models.TextField(blank=True)
#     attachment = models.FileField(upload_to='loan_attachments/', blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'loans'
#         ordering = ['-created_at']
    
#     def __str__(self):
#         return f'{self.member.full_name} - {self.amount}'
    
#     def get_balance(self):
#         total_paid = self.repayments.aggregate(total=models.Sum('amount'))['total'] or 0
#         return self.total_payable - total_paid
    
#     def is_completed(self):
#         return self.get_balance() <= 0
    
#     def approve(self, user):
#         if self.status == 'pending':
#             self.status = 'approved'
#             self.approval_date = timezone.now()
#             self.approved_by = user
#             self.save()
#             return True
#         return False
    
#     def activate(self):
#         if self.status == 'approved':
#             self.status = 'active'
#             self.save()
#             return True
#         return False

# class LoanRepayment(models.Model):
#     PAYMENT_METHODS = [
#         ('mpamba', 'Mpamba'),
#         ('airtel_money', 'Airtel Money'),
#         ('cash', 'Cash'),
#         ('bank_transfer', 'Bank Transfer'),
#     ]
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
#     member = models.ForeignKey(GroupMember, on_delete=models.CASCADE)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     principal_paid = models.DecimalField(max_digits=10, decimal_places=2)
#     interest_paid = models.DecimalField(max_digits=10, decimal_places=2)
#     payment_date = models.DateTimeField(auto_now_add=True)
#     payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
#     transaction_reference = models.CharField(max_length=100, blank=True)
#     recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
#     notes = models.TextField(blank=True)
    
#     class Meta:
#         db_table = 'loan_repayments'
#         ordering = ['-payment_date']
    
#     def __str__(self):
#         return f'{self.loan.member.full_name} - {self.amount}'

# class LoanRequest(models.Model):
#     """Requests to ECORET for loans"""
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('approved', 'Approved'),
#         ('declined', 'Declined'),
#         ('reviewing', 'Under Review'),
#     ]
    
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='loan_requests')
#     requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     purpose = models.TextField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
#     request_date = models.DateTimeField(auto_now_add=True)
#     approval_date = models.DateTimeField(null=True, blank=True)
#     notes = models.TextField(blank=True)
#     attachments = models.JSONField(default=list)
#     admin_notes = models.TextField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'loan_requests'
#         ordering = ['-request_date']
    
#     def __str__(self):
#         return f'{self.group.group_name} - {self.amount}'
    
#     def approve(self, user):
#         self.status = 'approved'
#         self.approval_date = timezone.now()
#         self.save()
    
#     def decline(self, user):
#         self.status = 'declined'
#         self.save()


# class LoanSettings(models.Model):
#     """Group loan settings with dynamic interest rates"""
#     group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='loan_settings')
    
#     default_interest_rate = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=10.00,
#         help_text="Default interest rate (%) for all loans"
#     )
#     group_loan_interest_rate = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=10.00,
#         help_text="Interest rate (%) for group loans. Set by group chairman."
#     )
    
#     group_loan_duration_months = models.IntegerField(
#         default=6,
#         help_text="Repayment duration in months for group loans. Set by group chairman."
#     )
    
#     group_loan_max_amount = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2,
#         default=500000,
#         help_text="Maximum group loan amount. Set by group chairman."
#     )
    
#     group_loan_min_amount = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2,
#         default=1000,
#         help_text="Minimum group loan amount. Set by group chairman."
#     )
    
#     ecoret_loan_interest_rate = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=5.00,
#         help_text="Interest rate (%) for ECORET loans. Set by ECORET admin."
#     )
    
#     ecoret_loan_duration_months = models.IntegerField(
#         default=12,
#         help_text="Repayment duration in months for ECORET loans. Set by ECORET admin."
#     )
    
#     ecoret_loan_max_amount = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2,
#         default=1000000,
#         help_text="Maximum ECORET loan amount. Set by ECORET admin."
#     )
    
#     ecoret_loan_min_amount = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2,
#         default=10000,
#         help_text="Minimum ECORET loan amount. Set by ECORET admin."
#     )
    
#     requires_guarantor = models.BooleanField(
#         default=True,
#         help_text="Does this group require a guarantor for loans?"
#     )
    
#     min_guarantors = models.IntegerField(
#         default=2,
#         help_text="Minimum number of guarantors required for loans."
#     )
    
#     grace_period_days = models.IntegerField(
#         default=7,
#         help_text="Days after due date before late fees apply."
#     )
    
#     late_fee_percentage = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=0,
#         help_text="Late fee as percentage of overdue amount."
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'loan_settings'
    
#     def __str__(self):
#         return f'Loan Settings - {self.group.group_name}'


# class ECORETSettings(models.Model):
#     """
#     Global settings for ECORET.
#     Only one instance should exist in the database.
#     """
    
#     ecoret_loan_interest_rate = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=5.00,
#         help_text="Current ECORET loan interest rate (%)"
#     )
    
#     ecoret_loan_duration_months = models.IntegerField(
#         default=12,
#         help_text="ECORET loan duration in months"
#     )
    
#     ecoret_loan_max_amount = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2,
#         default=1000000,
#         help_text="Maximum ECORET loan amount"
#     )
    
#     ecoret_loan_min_amount = models.DecimalField(
#         max_digits=10, 
#         decimal_places=2,
#         default=10000,
#         help_text="Minimum ECORET loan amount"
#     )
    
#     service_fee_percentage = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=2.5,
#         help_text="ECORET service fee (%) per transaction"
#     )
    
#     updated_by = models.ForeignKey(
#         User, 
#         on_delete=models.SET_NULL, 
#         null=True,
#         help_text="Admin who last updated these settings"
#     )
    
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'ecoret_settings'
#         verbose_name_plural = "ECORET Settings"
    
#     def __str__(self):
#         return "ECORET Loan Settings"
    
#     def save(self, *args, **kwargs):
#         if not self.pk and ECORETSettings.objects.exists():
#             raise Exception("ECORET settings already exist. Only one instance allowed.")
#         super().save(*args, **kwargs)



from django.db import models
from django.utils import timezone
from apps.groups.models import Group, GroupMember
from apps.accounts.models import User
import uuid


class Loan(models.Model):
    LOAN_TYPES = [
        ('group_loan', 'Group Loan'),  # Member ← Chairman (from group funds)
        ('ecoret_loan', 'ECORET Loan'),  # Chairman ← ECORET Admin (from ECORET funds)
    ]
    
    LOAN_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('defaulted', 'Defaulted'),
        ('declined', 'Declined'),
    ]
    
    # ECORET Admin Disbursement Methods (for ecoret_loan)
    ECORET_DISBURSEMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('pending', 'Pending - Awaiting Funds'),
    ]
    
    # Chairman Disbursement Methods (for group_loan)
    CHAIRMAN_DISBURSEMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('pending', 'Pending'),
    ]
    
    DISBURSEMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='loans')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_payable = models.DecimalField(max_digits=15, decimal_places=2)
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
    
    # ==================== ECORET DISBURSEMENT FIELDS (for ecoret_loan) ====================
    # These are used when ECORET Admin disburses to Group
    
    disbursement_method = models.CharField(
        max_length=20, 
        choices=ECORET_DISBURSEMENT_METHODS, 
        null=True, 
        blank=True
    )
    disbursement_status = models.CharField(
        max_length=20,
        choices=DISBURSEMENT_STATUS,
        default='pending'
    )
    disbursement_approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ecoret_disbursed_loans'
    )
    disbursement_date = models.DateTimeField(null=True, blank=True)
    disbursement_account = models.ForeignKey(
        'ECORETBankAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disbursed_loans'
    )
    
    # ECORET Cash Disbursement
    cash_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    
    # ECORET Bank Transfer Disbursement
    bank_transfer_reference = models.CharField(max_length=100, blank=True, null=True)
    ecoret_pin_verified = models.BooleanField(default=False)
    
    # ECORET Wait Disbursement
    wait_reason = models.TextField(blank=True, null=True)
    wait_reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wait_reported_loans'
    )
    wait_reported_at = models.DateTimeField(null=True, blank=True)
    
    # ==================== CHAIRMAN DISBURSEMENT FIELDS (for group_loan) ====================
    # These are used when Chairman disburses to Member
    
    chairman_disbursement_method = models.CharField(
        max_length=20,
        choices=CHAIRMAN_DISBURSEMENT_METHODS,
        null=True,
        blank=True
    )
    chairman_disbursement_status = models.CharField(
        max_length=20,
        choices=DISBURSEMENT_STATUS,
        default='pending'
    )
    chairman_disbursement_date = models.DateTimeField(null=True, blank=True)
    disbursed_by_chairman = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chairman_disbursed_loans'
    )
    
    # Chairman Cash Disbursement
    chairman_cash_receipt = models.CharField(max_length=50, blank=True, null=True)
    
    # Chairman Bank Transfer Disbursement
    chairman_transfer_reference = models.CharField(max_length=100, blank=True, null=True)
    
    # Chairman Mobile Money Disbursement
    chairman_mobile_money_reference = models.CharField(max_length=100, blank=True, null=True)
    chairman_mobile_money_provider = models.CharField(
        max_length=20,
        choices=(
            ('airtel', 'Airtel Money'),
            ('tnm', 'TNM Mpamba'),
        ),
        blank=True,
        null=True
    )
    
    # Chairman Disbursement Notes
    chairman_disbursement_notes = models.TextField(blank=True, null=True)
    
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
    
    # ==================== ECORET DISBURSEMENT METHODS ====================
    
    def mark_as_disbursed_by_ecoret(self, method, user, account=None, reference=None):
        """
        Mark loan as disbursed by ECORET Admin to Group
        Used for ecoret_loan type
        """
        self.disbursement_method = method
        self.disbursement_status = 'completed'
        self.disbursement_approved_by = user
        self.disbursement_date = timezone.now()
        self.status = 'active'
        self.approval_date = timezone.now()
        
        if method == 'cash':
            self.cash_receipt_number = reference or f"REC-{uuid.uuid4().hex[:8].upper()}"
        elif method == 'bank_transfer':
            self.bank_transfer_reference = reference
            self.ecoret_pin_verified = True
            self.disbursement_account = account
            
            if account:
                account.balance -= self.amount
                account.save()
        self.save()
    
    def mark_as_wait_by_ecoret(self, user, reason):
        """
        Mark loan as waiting for ECORET disbursement
        """
        self.disbursement_method = 'pending'
        self.disbursement_status = 'pending'
        self.wait_reason = reason
        self.wait_reported_by = user
        self.wait_reported_at = timezone.now()
        self.status = 'approved'  # Keep as approved, not active yet
        self.save()
    
    # ==================== CHAIRMAN DISBURSEMENT METHODS ====================
    
    def mark_as_disbursed_by_chairman(self, method, user, reference=None, provider=None, notes=None):
        """
        Mark loan as disbursed by Chairman to Member
        Used for group_loan type
        """
        self.chairman_disbursement_method = method
        self.chairman_disbursement_status = 'completed'
        self.chairman_disbursement_date = timezone.now()
        self.disbursed_by_chairman = user
        self.status = 'active'
        self.approval_date = timezone.now()
        
        if method == 'cash':
            self.chairman_cash_receipt = reference or f"REC-{uuid.uuid4().hex[:8].upper()}"
        elif method == 'bank_transfer':
            self.chairman_transfer_reference = reference
        elif method == 'mobile_money':
            self.chairman_mobile_money_reference = reference
            self.chairman_mobile_money_provider = provider
        
        if notes:
            self.chairman_disbursement_notes = notes
        
        self.save()
    
    def mark_as_wait_by_chairman(self, user, reason):
        """
        Mark loan as waiting for Chairman disbursement
        """
        self.chairman_disbursement_method = 'pending'
        self.chairman_disbursement_status = 'pending'
        self.chairman_disbursement_notes = reason
        self.status = 'approved'  # Keep as approved, not active yet
        self.save()
    
    # ==================== HELPER METHODS ====================
    
    def is_ecoret_loan(self):
        """Check if this is an ECORET loan"""
        return self.loan_type == 'ecoret_loan'
    
    def is_group_loan(self):
        """Check if this is a group loan (member personal loan)"""
        return self.loan_type == 'group_loan'
    
    def is_disbursed(self):
        """Check if loan has been disbursed"""
        return self.status == 'active'
    
    def get_disbursement_details(self):
        """Get disbursement details based on loan type"""
        if self.is_ecoret_loan():
            return {
                'method': self.disbursement_method,
                'status': self.disbursement_status,
                'approved_by': self.disbursement_approved_by,
                'date': self.disbursement_date,
                'cash_receipt': self.cash_receipt_number,
                'bank_reference': self.bank_transfer_reference,
                'wait_reason': self.wait_reason,
                'account': self.disbursement_account,
            }
        else:
            return {
                'method': self.chairman_disbursement_method,
                'status': self.chairman_disbursement_status,
                'approved_by': self.disbursed_by_chairman,
                'date': self.chairman_disbursement_date,
                'cash_receipt': self.chairman_cash_receipt,
                'bank_reference': self.chairman_transfer_reference,
                'mobile_money_reference': self.chairman_mobile_money_reference,
                'mobile_money_provider': self.chairman_mobile_money_provider,
                'notes': self.chairman_disbursement_notes,
            }


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
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    principal_paid = models.DecimalField(max_digits=15, decimal_places=2)
    interest_paid = models.DecimalField(max_digits=15, decimal_places=2)
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
    amount = models.DecimalField(max_digits=15, decimal_places=2)
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


class LoanSettings(models.Model):
    """Group loan settings with dynamic interest rates"""
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='loan_settings')
    
    default_interest_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=10.00,
        help_text="Default interest rate (%) for all loans"
    )
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
        max_digits=15, 
        decimal_places=2,
        default=500000,
        help_text="Maximum group loan amount. Set by group chairman."
    )
    
    group_loan_min_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=1000,
        help_text="Minimum group loan amount. Set by group chairman."
    )
    
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
        max_digits=15, 
        decimal_places=2,
        default=1000000,
        help_text="Maximum ECORET loan amount. Set by ECORET admin."
    )
    
    ecoret_loan_min_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=10000,
        help_text="Minimum ECORET loan amount. Set by ECORET admin."
    )
    
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


class ECORETSettings(models.Model):
    """
    Global settings for ECORET.
    Only one instance should exist in the database.
    """
    
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
        max_digits=15, 
        decimal_places=2,
        default=1000000,
        help_text="Maximum ECORET loan amount"
    )
    
    ecoret_loan_min_amount = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=10000,
        help_text="Minimum ECORET loan amount"
    )
    
    service_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=2.5,
        help_text="ECORET service fee (%) per transaction"
    )
    
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
        if not self.pk and ECORETSettings.objects.exists():
            raise Exception("ECORET settings already exist. Only one instance allowed.")
        super().save(*args, **kwargs)


# apps/loans/models.py

class ECORETBankAccount(models.Model):
    """
    ECORET Bank Accounts for disbursement
    """
    
    ACCOUNT_TYPES = [
        ('main', 'Main Account'),
        ('disbursement', 'Disbursement Account'),
        ('settlement', 'Settlement Account'),
        ('escrow', 'Escrow Account'),
    ]
    
    ACCOUNT_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('pending_verification', 'Pending Verification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Account nickname (e.g., 'ECORET Main')")
    account_number = models.CharField(max_length=50, unique=True)
    account_name = models.CharField(max_length=200)
    bank_name = models.CharField(max_length=100)
    bank_branch = models.CharField(max_length=100, blank=True)
    bank_code = models.CharField(max_length=20, blank=True, help_text="Bank code for PayChangu")
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='main')
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS, default='pending_verification')
    currency = models.CharField(max_length=3, default='MWK')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # PayChangu specific fields
    paychangu_account_id = models.CharField(max_length=100, blank=True, null=True)
    paychangu_verified = models.BooleanField(default=False)
    paychangu_verification_date = models.DateTimeField(null=True, blank=True)
    
    # Account limits
    daily_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    transaction_limit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ecoret_bank_accounts'
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.account_number} ({self.bank_name})"
    
    def verify_with_paychangu(self):
        """Verify bank account with PayChangu"""
        self.status = 'active'
        self.paychangu_verified = True
        self.paychangu_verification_date = timezone.now()
        self.save()
        return True
    
    def has_sufficient_balance(self, amount):
        """Check if account has sufficient balance"""
        return self.balance >= amount
    
    def get_account_details(self):
        """Get formatted account details"""
        return {
            'id': str(self.id),
            'name': self.name,
            'account_number': self.account_number,
            'account_name': self.account_name,
            'bank_name': self.bank_name,
            'bank_branch': self.bank_branch,
            'account_type': self.account_type,
            'balance': float(self.balance),
            'currency': self.currency,
            'is_default': self.is_default,
            'status': self.status,
        }

        