from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
import logging
from apps.groups.models import GroupMember
from .models import (
    Loan, LoanRepayment, LoanRequest, LoanSettings, 
    ECORETSettings, ECORETBankAccount
)
import json
logger = logging.getLogger(__name__)

class ECORETBankAccountSerializer(serializers.ModelSerializer):
    account_type_display = serializers.CharField(
        source='get_account_type_display', 
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    
    class Meta:
        model = ECORETBankAccount
        fields = [
            'id', 'name', 'account_number', 'account_name', 'bank_name',
            'bank_branch', 'bank_code', 'account_type', 'account_type_display',
            'status', 'status_display', 'balance', 'currency',
            'daily_limit', 'transaction_limit', 'is_default',
            'paychangu_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LoanRepaymentSerializer(serializers.ModelSerializer):
    """Serializer for loan repayments"""
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    
    class Meta:
        model = LoanRepayment
        fields = [
            'id', 'loan', 'member', 'member_name',
            'amount', 'principal_paid', 'interest_paid', 
            'payment_method', 'transaction_reference', 'notes',
            'payment_date', 'recorded_by','recorded_at'
        ]
        read_only_fields = ['id', 'payment_date', 'recorded_at']

class LoanRepaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating loan repayments"""
    
    class Meta:
        model = LoanRepayment
        fields = [
            'id', 'loan', 'amount', 'payment_method',
            'transaction_reference', 'notes'
        ]
    
    def validate(self, data):
        """Validate the repayment data"""
        loan = self.context.get('loan')
        if not loan:
            raise serializers.ValidationError("Loan context is required")
        
        amount = data.get('amount', 0)
        
        if loan.status not in ['active', 'approved']:
            raise serializers.ValidationError(
                f"Cannot make repayment on this loan. Current status: {loan.status}"
            )
        
        if amount <= 0:
            raise serializers.ValidationError("Repayment amount must be greater than zero")
        
        balance = loan.get_balance()
        if amount > balance:
            raise serializers.ValidationError(
                f"Amount exceeds balance. Balance: {balance}"
            )
        
        return data
    
    def create(self, validated_data):
        """Create the repayment with calculated principal and interest"""
        loan = self.context.get('loan')
        request = self.context.get('request')
        amount = validated_data.get('amount', 0)
        
        total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0
        remaining_principal = loan.total_payable - total_paid
        
        if amount <= remaining_principal:
            principal_paid = amount
            interest_paid = 0
        else:
            principal_paid = remaining_principal
            interest_paid = amount - remaining_principal
        
        repayment = LoanRepayment.objects.create(
            loan=loan,
            member=loan.member,
            recorded_by=request.user if request else None,
            amount=amount,
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            payment_method=validated_data.get('payment_method', 'cash'),
            transaction_reference=validated_data.get('transaction_reference', ''),
            notes=validated_data.get('notes', ''),
            payment_date=timezone.now()
        )
        
        if loan.get_balance() <= 0:
            loan.status = 'completed'
            loan.save()
            logger.info(f"✅ Loan {loan.id} automatically marked as completed")
        
        return repayment

class LoanSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    balance = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    repayments = LoanRepaymentSerializer(many=True, read_only=True, source='repayment_set')
    
    disbursement_method_display = serializers.CharField(
        source='get_disbursement_method_display', 
        read_only=True
    )
    disbursement_status_display = serializers.CharField(
        source='get_disbursement_status_display', 
        read_only=True
    )
    
    chairman_disbursement_method_display = serializers.CharField(
        source='get_chairman_disbursement_method_display',
        read_only=True
    )
    chairman_disbursement_status_display = serializers.CharField(
        source='get_chairman_disbursement_status_display',
        read_only=True
    )
    
    disbursement_account_details = serializers.SerializerMethodField()
    disbursed_by_chairman_name = serializers.CharField(
        source='disbursed_by_chairman.get_full_name',
        read_only=True
    )
    
    class Meta:
        model = Loan
        fields = [
            'id', 'group', 'group_name', 'member', 'member_name', 'loan_type',
            'amount', 'interest_rate', 'total_payable', 'duration_months',
            'purpose', 'otp', 'status', 'request_date', 'approval_date', 'due_date',
            'notes', 'attachment', 'created_at', 'updated_at', 'balance', 'total_paid',
            'disbursement_method', 'disbursement_method_display',
            'disbursement_status', 'disbursement_status_display',
            'disbursement_approved_by', 'disbursement_date',
            'cash_receipt_number', 'bank_transfer_reference',
            'wait_reason', 'wait_reported_by', 'wait_reported_at',
            'disbursement_account', 'disbursement_account_details',
            'ecoret_pin_verified',
            'chairman_disbursement_method', 'chairman_disbursement_method_display',
            'chairman_disbursement_status', 'chairman_disbursement_status_display',
            'chairman_disbursement_date', 'disbursed_by_chairman',
            'disbursed_by_chairman_name', 'chairman_cash_receipt',
            'chairman_transfer_reference', 'chairman_mobile_money_reference',
            'chairman_mobile_money_provider', 'chairman_disbursement_notes',
            
            'repayments',
        ]
        read_only_fields = ['id', 'request_date', 'created_at', 'updated_at']
    
    def get_balance(self, obj):
        return obj.get_balance()
    
    def get_total_paid(self, obj):
        return obj.repayments.aggregate(total=serializers.models.Sum('amount'))['total'] or Decimal('0')
    
    def get_disbursement_account_details(self, obj):
        if obj.disbursement_account:
            return ECORETBankAccountSerializer(obj.disbursement_account).data
        return None


class LoanUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['status', 'notes']


class LoanCreateSerializer(serializers.ModelSerializer):
    attachment = serializers.JSONField(required=False, allow_null=True, default=dict)
    
    class Meta:
        model = Loan
        fields = ['member', 'loan_type', 'amount', 'interest_rate', 
                 'duration_months', 'purpose', 'attachment']
        extra_kwargs = {
            'interest_rate': {'required': False, 'allow_null': True},
            'duration_months': {'required': False, 'allow_null': True},
        }
    
    def validate_attachment(self, value):
        """Validate attachment field to handle various input formats"""
        if value is None:
            return {}
        
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON format for attachment")
        
        if not isinstance(value, (dict, list)):
            raise serializers.ValidationError("Attachment must be a JSON object or array")
        
        return value
    
    def validate(self, data):
        amount = data.get('amount')
        
        if amount is None:
            raise serializers.ValidationError({'amount': 'Amount is required'})
        
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
                data['amount'] = amount
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
                data['interest_rate'] = interest_rate
            except:
                interest_rate = Decimal('0')
        
        interest = amount * (interest_rate / Decimal('100'))
        data['total_payable'] = amount + interest
        
        duration_months = data.get('duration_months')
        if duration_months:
            if not isinstance(duration_months, int):
                try:
                    duration_months = int(duration_months)
                    data['duration_months'] = duration_months
                except:
                    duration_months = 1
        else:
            duration_months = 1
            data['duration_months'] = duration_months
        
        data['due_date'] = timezone.now() + timezone.timedelta(days=duration_months * 30)
        
        return data

class LoanDisbursementSerializer(serializers.Serializer):
    """
    Serializer for validating loan disbursement data
    """
    disbursement_method = serializers.ChoiceField(
        choices=['cash', 'bank_transfer', 'wait']
    )
    bank_account_id = serializers.UUIDField(required=False, allow_null=True)
    pin = serializers.CharField(required=False, allow_blank=True, max_length=128)
    receipt_number = serializers.CharField(required=False, allow_blank=True)
    transfer_reference = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        method = data.get('disbursement_method')
        
        if method == 'cash':
            if not data.get('receipt_number'):
                raise serializers.ValidationError({
                    'receipt_number': 'Cash receipt number is required'
                })
        
        elif method == 'bank_transfer':
            if not data.get('bank_account_id'):
                raise serializers.ValidationError({
                    'bank_account_id': 'Bank account selection is required'
                })
            if not data.get('pin'):
                raise serializers.ValidationError({
                    'pin': 'PIN is required for bank transfer'
                })
            if not data.get('transfer_reference'):
                raise serializers.ValidationError({
                    'transfer_reference': 'Transfer reference is required'
                })
        
        elif method == 'wait':
            if not data.get('reason'):
                raise serializers.ValidationError({
                    'reason': 'Reason is required for wait'
                })
        
        return data


class ChairmanDisbursementSerializer(serializers.Serializer):
    """
    Serializer for validating chairman disbursement data
    """
    disbursement_method = serializers.ChoiceField(
        choices=['cash', 'bank_transfer', 'mobile_money']
    )
    receipt_number = serializers.CharField(required=False, allow_blank=True)
    transfer_reference = serializers.CharField(required=False, allow_blank=True)
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    mobile_money_provider = serializers.ChoiceField(
        choices=['airtel', 'tnm'],
        required=False,
        allow_blank=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        method = data.get('disbursement_method')
        
        if method == 'cash':
            if not data.get('receipt_number'):
                raise serializers.ValidationError({
                    'receipt_number': 'Cash receipt number is required'
                })
        
        elif method == 'bank_transfer':
            if not data.get('transfer_reference'):
                raise serializers.ValidationError({
                    'transfer_reference': 'Transfer reference is required'
                })
        
        elif method == 'mobile_money':
            if not data.get('transaction_id'):
                raise serializers.ValidationError({
                    'transaction_id': 'Mobile money transaction ID is required'
                })
            if not data.get('mobile_money_provider'):
                raise serializers.ValidationError({
                    'mobile_money_provider': 'Mobile money provider is required'
                })
        
        return data

class LoanRequestSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)

    class Meta:
        model = LoanRequest
        fields = [
            'id', 'group', 'group_name', 'requested_by', 'requested_by_name',
            'amount', 'approved_amount', 'purpose', 'status', 'request_date', 'approval_date',
            'notes', 'attachments', 'document', 'admin_notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'request_date', 'created_at', 'updated_at', 'approved_amount']


class LoanRequestCreateSerializer(serializers.ModelSerializer):
    attachments = serializers.JSONField(required=False, allow_null=True, default=list)
    document = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = LoanRequest
        fields = ['amount', 'purpose', 'notes', 'attachments', 'document']

    def validate_attachments(self, value):
        """Validate attachments field to handle various input formats"""
        if value is None:
            return []

        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON format for attachments")

        if not isinstance(value, list):
            raise serializers.ValidationError("Attachments must be a JSON array")

        return value

    def validate(self, data):
        amount = data.get('amount', 0)
        if not isinstance(amount, Decimal):
            try:
                amount = Decimal(str(amount))
            except:
                raise serializers.ValidationError({'amount': 'Invalid amount format'})
        if amount <= 0:
            raise serializers.ValidationError({'amount': 'Amount must be greater than 0'})
        return data

class LoanSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanSettings
        fields = [
            'id', 'group',
            'default_interest_rate',
            'group_loan_interest_rate',
            'group_loan_duration_months',
            'group_loan_min_amount',
            'group_loan_max_amount',
            'ecoret_loan_interest_rate',
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

class ECORETSettingsSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = ECORETSettings
        fields = [
            'id', 'ecoret_loan_interest_rate', 'ecoret_loan_duration_months',
            'ecoret_loan_max_amount', 'ecoret_loan_min_amount',
            'service_fee_percentage', 'updated_by', 'updated_by_name',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']