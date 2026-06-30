from rest_framework import serializers
from .models import Attendance, Meeting, ParticipationTracking
from apps.groups.serializers import GroupMemberSerializer
from .models import AttendanceCase, PenaltyPayment

class AttendanceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'group', 'group_name', 'member', 'member_name',
            'meeting_date', 'meeting_type', 'attended', 'time_in',
            'time_out', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class AttendanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ['member', 'meeting_date', 'meeting_type', 'attended', 'time_in', 'time_out', 'notes']
    
    def validate(self, data):
        # Check if attendance already exists for this member and date
        if Attendance.objects.filter(
            member=data['member'],
            meeting_date=data['meeting_date']
        ).exists():
            raise serializers.ValidationError(
                'Attendance already recorded for this member on this date'
            )
        return data

class MeetingSerializer(serializers.ModelSerializer):
    attendance_count = serializers.SerializerMethodField()
    total_members = serializers.SerializerMethodField()
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    
    class Meta:
        model = Meeting
        fields = [
            'id', 'group', 'group_name', 'title', 'meeting_date',
            'start_time', 'end_time', 'meeting_type', 'agenda',
            'minutes', 'location', 'is_completed', 'created_by',
            'attendance_count', 'total_members', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_attendance_count(self, obj):
        return obj.get_attendance_count()
    
    def get_total_members(self, obj):
        return obj.get_total_members()

class MeetingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['title', 'meeting_date', 'start_time', 'end_time', 
                 'meeting_type', 'agenda', 'location']

class ParticipationTrackingSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    
    class Meta:
        model = ParticipationTracking
        fields = [
            'id', 'member', 'member_name', 'meeting_date',
            'participated', 'contribution', 'points', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

# ... existing serializers ...

class AttendanceCaseSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)
    penalty_balance = serializers.SerializerMethodField()
    is_fully_paid = serializers.SerializerMethodField()
    
    class Meta:
        model = AttendanceCase
        fields = [
            'id', 'group', 'member', 'member_name', 'meeting', 'meeting_date',
            'case_type', 'reason', 'penalty_amount', 'penalty_paid',
            'penalty_balance', 'penalty_due_date', 'status', 'notes',
            'recorded_by', 'recorded_by_name', 'resolved_by', 'resolved_by_name',
            'resolved_at', 'created_at', 'updated_at', 'is_fully_paid'
        ]
        read_only_fields = ['id', 'penalty_paid', 'penalty_balance', 'created_at', 'updated_at']
    
    def get_penalty_balance(self, obj):
        return obj.get_penalty_balance()
    
    def get_is_fully_paid(self, obj):
        return obj.is_fully_paid()


class AttendanceCaseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceCase
        fields = [
            'member', 'meeting', 'meeting_date', 'case_type',
            'reason', 'penalty_amount', 'penalty_due_date', 'notes'
        ]
    
    def validate_penalty_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('Penalty amount cannot be negative')
        return value


class PenaltyPaymentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = PenaltyPayment
        fields = [
            'id', 'group', 'member', 'member_name', 'attendance_case',
            'amount', 'payment_method', 'transaction_reference',
            'payment_date', 'notes', 'recorded_by', 'recorded_by_name'
        ]
        read_only_fields = ['id', 'payment_date']


class PenaltyPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PenaltyPayment
        fields = ['amount', 'payment_method', 'transaction_reference', 'notes']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero')
        return value        