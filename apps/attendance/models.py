from django.db import models
from django.utils import timezone
from apps.groups.models import Group, GroupMember
from apps.accounts.models import User
import uuid

class Attendance(models.Model):
    MEETING_TYPES = [
        ('regular', 'Regular Meeting'),
        ('special', 'Special Meeting'),
        ('annual', 'Annual General Meeting'),
        ('emergency', 'Emergency Meeting'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='attendances')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='attendances')
    meeting_date = models.DateField(db_index=True)
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPES, default='regular')
    attended = models.BooleanField(default=False)
    time_in = models.DateTimeField(null=True, blank=True)
    time_out = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance'
        ordering = ['-meeting_date', 'member__full_name']
        unique_together = ['member', 'meeting_date']
    
    def __str__(self):
        return f'{self.member.full_name} - {self.meeting_date}'

class Meeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='meetings')
    title = models.CharField(max_length=255)
    meeting_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    meeting_type = models.CharField(max_length=20, choices=Attendance.MEETING_TYPES, default='regular')
    agenda = models.TextField(blank=True)
    minutes = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    is_completed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'meetings'
        ordering = ['-meeting_date']
    
    def __str__(self):
        return f'{self.title} - {self.meeting_date}'
    
    def get_attendance_count(self):
        """Get number of attendees for this meeting"""
        from .models import Attendance
        return Attendance.objects.filter(
            group=self.group,
            meeting_date=self.meeting_date,
            attended=True
        ).count()
    
    def get_total_members(self):
        return self.group.members.filter(is_active=True).count()

class ParticipationTracking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='participation')
    meeting_date = models.DateField()
    participated = models.BooleanField(default=False)
    contribution = models.TextField(blank=True)
    points = models.IntegerField(default=0)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'participation_tracking'
        unique_together = ['member', 'meeting_date']
        ordering = ['-meeting_date']
    
    
class AttendanceCase(models.Model):
    """
    📋 Track attendance-related cases (late coming, absence, etc.)
    This is separate from regular attendance tracking
    """
    
    CASE_TYPES = [
        ('late_coming', 'Late Coming'),
        ('absence', 'Absence'),
        ('early_departure', 'Early Departure'),
        ('no_excuse', 'No Excuse'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('waived', 'Waived'),
        ('appealed', 'Appealed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='attendance_cases')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='attendance_cases')
    meeting = models.ForeignKey('Meeting', on_delete=models.CASCADE, null=True, blank=True, related_name='cases')
    meeting_date = models.DateField()
    
    case_type = models.CharField(max_length=20, choices=CASE_TYPES)
    reason = models.TextField(blank=True)
    
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penalty_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penalty_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penalty_due_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_cases')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='resolved_cases')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'attendance_cases'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.member.full_name} - {self.case_type} ({self.meeting_date})"
    
    def get_penalty_balance(self):
        """Calculate remaining penalty balance"""
        return self.penalty_amount - self.penalty_paid
    
    def is_fully_paid(self):
        """Check if penalty is fully paid"""
        return self.get_penalty_balance() <= 0
    
    def add_payment(self, amount):
        """Add penalty payment"""
        self.penalty_paid += amount
        self.save()
        if self.is_fully_paid():
            self.status = 'resolved'
            self.save()
        return True


class PenaltyPayment(models.Model):
    """
    💰 Track penalty payments separately from savings
    """
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpamba', 'Mpamba'),
        ('airtel_money', 'Airtel Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('deduction', 'Deducted from Savings'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='penalty_payments')
    member = models.ForeignKey(GroupMember, on_delete=models.CASCADE, related_name='penalty_payments')
    attendance_case = models.ForeignKey(AttendanceCase, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_reference = models.CharField(max_length=100, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'penalty_payments'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.member.full_name} - MK{self.amount} - {self.payment_method}"