from django.db import models
from django.utils import timezone
from apps.groups.models import Group, GroupMember
from apps.accounts.models import User
import uuid

class Saving(models.Model):
    SAVING_TYPES = [
        ('voluntary', 'Voluntary'),
        ('compulsory', 'Compulsory'),
    ]
    
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='savings')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='savings')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    saving_type = models.CharField(max_length=20, choices=SAVING_TYPES, default='voluntary')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    transaction_date = models.DateTimeField(auto_now_add=True)
    reference_number = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'savings'
        ordering = ['-transaction_date']
    
    def __str__(self):
        return f'{self.member.full_name} - {self.amount} ({self.transaction_type})'

class SavingGoal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='saving_goals')
    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    target_date = models.DateField()
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'saving_goals'
        ordering = ['target_date']
    
    def __str__(self):
        return f'{self.name} - {self.group.group_name}'
    
    def get_progress_percentage(self):
        if self.target_amount == 0:
            return 0
        return (self.current_amount / self.target_amount) * 100

class SavingSummary(models.Model):
    """Daily summary of savings"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='saving_summaries')
    date = models.DateField()
    total_deposits = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_withdrawals = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deposit_count = models.IntegerField(default=0)
    total_withdrawal_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'saving_summaries'
        unique_together = ['group', 'date']
        ordering = ['-date']