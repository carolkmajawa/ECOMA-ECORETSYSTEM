from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from apps.accounts.models import User
import uuid


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_name = models.CharField(max_length=255, db_index=True)
    group_code = models.CharField(max_length=20, unique=True, blank=True, null=True, db_index=True)
    chairman = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='chairman_groups'
    )
    secretary = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='secretary_groups'
    )
    treasurer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='treasurer_groups'
    )

    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    billing_number = models.CharField(max_length=50, blank=True, null=True)
    bank_account_name = models.CharField(max_length=200, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)

    mobile_money_provider = models.CharField(
        max_length=20,
        choices=[
            ('mpamba', 'Mpamba'),
            ('airtel_money', 'Airtel Money'),
            ('tnm_mpamba', 'TNM Mpamba'),
            ('other', 'Other')
        ],
        blank=True,
        null=True
    )
    mobile_money_number = models.CharField(max_length=20, blank=True, null=True)

    ecoret_account_id = models.CharField(max_length=50, blank=True, null=True)
    ecoret_billing_code = models.CharField(max_length=50, blank=True, null=True)

    virtual_account_number = models.CharField(max_length=50, blank=True, null=True)
    virtual_account_holder = models.CharField(max_length=200, blank=True, null=True)

    daily_transaction_limit = models.DecimalField(max_digits=10, decimal_places=2, default=1000000)
    max_loan_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500000)

    default_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        help_text="Default interest rate (%) for all loans (Group and ECORET)"
    )

    social_max_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=5000.00,
        help_text="Maximum amount a member can contribute to social fund per cycle"
    )

    savings_max_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10000.00,
        help_text="Maximum savings contribution per member per cycle"
    )

    savings_min_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500.00,
        help_text="Minimum savings contribution per member per cycle"
    )

    cycle_start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the current group cycle starts"
    )

    cycle_end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when the current group cycle ends"
    )

    cycle_duration_months = models.IntegerField(
        default=6,
        help_text="Duration of each group cycle in months"
    )

    is_cycle_active = models.BooleanField(
        default=False,
        help_text="Whether the current cycle is active"
    )

    meeting_frequency = models.CharField(
        max_length=20,
        choices=[
            ('weekly', 'Weekly'),
            ('biweekly', 'Bi-Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='weekly',
        help_text="How often the group meets"
    )

    meeting_day = models.CharField(
        max_length=10,
        choices=[
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
            ('sunday', 'Sunday'),
        ],
        default='saturday',
        help_text="Which day of the week the group meets"
    )

    address = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to='group_photos/', blank=True, null=True)
    is_active = models.BooleanField(default=False)
    activation_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'groups'
        ordering = ['-created_at']

    def __str__(self):
        return self.group_name

    def activate(self):
        if not self.is_active:
            import random
            import string
            while True:
                code = ''.join(random.choices(string.digits, k=6))
                if not Group.objects.filter(group_code=code).exists():
                    self.group_code = code
                    break
            self.is_active = True
            self.activation_date = timezone.now()
            self.save()
            return self.group_code
        return None

    def get_member_count(self):
        return self.members.filter(is_active=True).count()

    def start_new_cycle(self, start_date=None, duration_months=None):
        from django.utils import timezone
        from datetime import timedelta

        if not start_date:
            start_date = timezone.now().date()

        if isinstance(start_date, str):
            from datetime import datetime
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

        if hasattr(start_date, 'date'):
            start_date = start_date.date()

        self.cycle_start_date = start_date

        if duration_months:
            self.cycle_duration_months = int(duration_months)

        days_to_add = self.cycle_duration_months * 30
        self.cycle_end_date = start_date + timedelta(days=days_to_add)

        self.is_cycle_active = True
        self.save()

        return {
            'start_date': self.cycle_start_date,
            'end_date': self.cycle_end_date,
            'duration_months': self.cycle_duration_months
        }

    def end_current_cycle(self):
        self.is_cycle_active = False
        self.save()
        return {'message': 'Cycle ended successfully'}

    def get_cycle_progress(self):
        from django.utils import timezone

        if not self.is_cycle_active or not self.cycle_start_date:
            return None

        today = timezone.now().date()
        total_days = (self.cycle_end_date - self.cycle_start_date).days
        elapsed_days = (today - self.cycle_start_date).days

        if total_days <= 0:
            return 100

        progress = min(100, (elapsed_days / total_days) * 100)

        return {
            'progress': round(progress, 2),
            'elapsed_days': elapsed_days,
            'total_days': total_days,
            'remaining_days': max(0, total_days - elapsed_days)
        }

    def get_cycle_status(self):
        from django.utils import timezone

        if not self.is_cycle_active:
            return 'Not Active'

        if self.cycle_end_date:
            if timezone.now().date() > self.cycle_end_date:
                return 'Ended'
            return 'Active'

        return 'No Cycle'


class GroupMember(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    BUSINESS_TYPES = [
        ('farming', 'Farming'),
        ('trading', 'Trading/Shop'),
        ('retail', 'Retail Business'),
        ('salaried', 'Salaried Employment'),
        ('artisan', 'Artisan/Craft'),
        ('transport', 'Transport'),
        ('fishing', 'Fishing'),
        ('livestock', 'Livestock Rearing'),
        ('food_vendor', 'Food Vendor'),
        ('salon', 'Salon/Barber'),
        ('tailor', 'Tailoring/Sewing'),
        ('construction', 'Construction'),
        ('mining', 'Mining'),
        ('student', 'Student'),
        ('homemaker', 'Homemaker'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='group_memberships'
    )
    full_name = models.CharField(max_length=255)
    national_id = models.CharField(max_length=50, db_index=True)
    national_id_photo = models.ImageField(upload_to='national_ids/', blank=True, null=True)
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+?[0-9]{10,15}$')],
        db_index=True
    )
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    address = models.TextField(blank=True)

    business_type = models.CharField(
        max_length=30,
        choices=BUSINESS_TYPES,
        blank=True,
        null=True,
        help_text="Type of business/occupation the member does"
    )
    business_description = models.TextField(
        blank=True,
        null=True,
        help_text="Detailed description of the member's business"
    )

    is_active = models.BooleanField(default=True)
    joined_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ==================== BANK DETAILS (for member to receive money) ====================
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_name = models.CharField(max_length=200, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)
    
    # ==================== MOBILE MONEY DETAILS (for member to receive money) ====================
    mobile_money_provider = models.CharField(
        max_length=20,
        choices=(
            ('airtel', 'Airtel Money'),
            ('tnm', 'TNM Mpamba'),
        ),
        blank=True,
        null=True
    )
    mobile_money_number = models.CharField(max_length=15, blank=True, null=True)

    class Meta:
        db_table = 'group_members'
        ordering = ['full_name']
        unique_together = ['group', 'user']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'phone_number'],
                name='unique_group_phone'
            ),
            models.UniqueConstraint(
                fields=['group', 'national_id'],
                name='unique_group_national_id'
            )
        ]

    def __str__(self):
        return f'{self.full_name} - {self.group.group_name}'

    def get_attendance_percentage(self):
        total_meetings = self.attendances.count()
        if total_meetings == 0:
            return 0
        attended = self.attendances.filter(attended=True).count()
        return (attended / total_meetings) * 100

    def has_bank_details(self):
        """Check if member has bank details"""
        return bool(self.bank_account_number)
    
    def has_mobile_money(self):
        """Check if member has mobile money"""
        return bool(self.mobile_money_number)
    
    def get_disbursement_options(self):
        """Get available disbursement methods for this member"""
        options = []
        if self.has_bank_details():
            options.append('bank_transfer')
        if self.has_mobile_money():
            options.append('mobile_money')
        options.append('cash')  # Cash is always available
        return options
    
class GroupRecord(models.Model):
    RECORD_TYPES = [
        ('meeting_minutes', 'Meeting Minutes'),
        ('financial_report', 'Financial Report'),
        ('constitution', 'Constitution'),
        ('member_list', 'Member List'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='records')
    record_name = models.CharField(max_length=255)
    record_type = models.CharField(max_length=50, choices=RECORD_TYPES)
    file = models.FileField(upload_to='group_records/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_records'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.record_name} - {self.group.group_name}'