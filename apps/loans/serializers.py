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

class LoanUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating loan details"""
    class Meta:
        model = Loan
        fields = ['status', 'notes']

class LoanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['member', 'loan_type', 'amount', 'interest_rate', 
                 'duration_months', 'purpose', 'attachment']
        extra_kwargs = {
            'interest_rate': {'required': False, 'allow_null': True},
            'duration_months': {'required': False, 'allow_null': True},
        }
    
    def validate(self, data):
        amount = data.get('amount')
        
        if amount is None:
            raise serializers.ValidationError({'amount': 'Amount is required'})
        
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except:
                raise serializers.ValidationError({'amount': 'Invalid amount format'})
        
        if amount <= 0:
            raise serializers.ValidationError({'amount': 'Amount must be greater than 0'})
        
        interest_rate = data.get('interest_rate', Decimal('0'))
        if interest_rate is None:
            interest_rate = Decimal('0')
        elif not isinstance(interest_rate, Decimal):
            try:
                interest_rate = Decimal(str(interest_rate))
            except:
                interest_rate = Decimal('0')
        
        interest = amount * (interest_rate / Decimal('100'))
        data['total_payable'] = amount + interest
        
        duration_months = data.get('duration_months')
        if duration_months:
            if not isinstance(duration_months, int):
                try:
                    duration_months = int(duration_months)
                except:
                    duration_months = 1
        else:
            duration_months = 1
        
        data['due_date'] = timezone.now() + timezone.timedelta(days=duration_months * 30)
        data['duration_months'] = duration_months
        
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
            'id', 'group',
            'default_interest_rate',
            'group_loan_duration_months',
            'group_loan_min_amount',
            'group_loan_max_amount',
            'ecoret_loan_duration_months',
            'ecoret_loan_min_amount',
            'ecoret_loan_max_amount',
            'requires_guarantor',
            'min_guarantors',
            'grace_period_days',
            'late_fee_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']