from rest_framework import serializers
from django.utils import timezone
from decimal import Decimal 
from .models import Loan, LoanRepayment, LoanRequest, LoanSettings


class LoanSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    balance = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    
    class Meta:
        model = Loan
        fields = [
            'id', 'group', 'group_name', 'member', 'member_name', 'loan_type',
            'amount', 'interest_rate', 'total_payable', 'duration_months',
            'purpose', 'status', 'request_date', 'approval_date', 'due_date',
            'notes', 'attachment', 'created_at', 'updated_at', 'balance', 'total_paid'
        ]
        read_only_fields = ['id', 'request_date', 'created_at', 'updated_at']
    
    def get_balance(self, obj):
        return obj.get_balance()
    
    def get_total_paid(self, obj):
        return obj.repayments.aggregate(total=serializers.models.Sum('amount'))['total'] or Decimal('0')


class LoanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['member', 'loan_type', 'amount', 'interest_rate', 
                 'duration_months', 'purpose', 'attachment']
    
    def validate(self, data):
        amount = data.get('amount')
        
        # ✅ Convert to Decimal if needed
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        
        if amount <= 0:
            raise serializers.ValidationError('Amount must be greater than 0')
        
        # ✅ Get interest rate and convert to Decimal
        interest_rate = data.get('interest_rate', Decimal('0'))
        if not isinstance(interest_rate, Decimal):
            interest_rate = Decimal(str(interest_rate))
        
        # ✅ Calculate total payable (using Decimal)
        interest = amount * (interest_rate / Decimal('100'))
        data['total_payable'] = amount + interest
        
        # Set due date
        duration_months = data.get('duration_months', 1)
        data['due_date'] = timezone.now() + timezone.timedelta(days=duration_months * 30)
        
        return data


class LoanRepaymentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    
    class Meta:
        model = LoanRepayment
        fields = [
            'id', 'loan', 'member', 'member_name', 'amount', 
            'principal_paid', 'interest_paid', 'payment_date', 
            'payment_method', 'transaction_reference', 'recorded_by',
            'recorded_by_name', 'notes'
        ]
        read_only_fields = ['id', 'payment_date']


class LoanRepaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRepayment
        fields = ['amount', 'payment_method', 'transaction_reference', 'notes']
    
    def validate(self, data):
        amount = data.get('amount')
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if amount <= 0:
            raise serializers.ValidationError('Amount must be greater than 0')
        return data


class LoanRequestSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    
    class Meta:
        model = LoanRequest
        fields = [
            'id', 'group', 'group_name', 'requested_by', 'requested_by_name',
            'amount', 'purpose', 'status', 'request_date', 'approval_date',
            'notes', 'attachments', 'admin_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'request_date', 'created_at', 'updated_at']


class LoanRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRequest
        fields = ['amount', 'purpose', 'notes', 'attachments']
    
    def validate(self, data):
        amount = data.get('amount', 0)
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if amount <= 0:
            raise serializers.ValidationError('Amount must be greater than 0')
        return data


class LoanSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanSettings
        fields = [
            'max_loan_amount', 'default_interest_rate', 'min_duration_months',
            'max_duration_months', 'requires_guarantor', 'min_guarantors'
        ]