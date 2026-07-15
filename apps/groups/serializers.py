from rest_framework import serializers
from .models import Group, GroupMember, GroupRecord
from apps.accounts.serializers import UserSerializer

class GroupBankAccountSerializer(serializers.ModelSerializer):
    """Serializer for group bank account details"""
    
    class Meta:
        model = Group
        fields = [
            'bank_name',
            'bank_account_number',
            'bank_account_name',
            'bank_branch',
            'mobile_money_provider',
            'mobile_money_number',
            'ecoret_account_id',
            'ecoret_billing_code',
            'virtual_account_number',
            'virtual_account_holder',
            'daily_transaction_limit',
            'max_loan_amount'
        ]

class GroupBankAccountUpdateSerializer(serializers.Serializer):
    """Serializer for updating bank account details"""
    
    bank_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bank_account_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bank_account_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bank_branch = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    mobile_money_provider = serializers.ChoiceField(
        choices=['mpamba', 'airtel_money', 'tnm_mpamba', 'other'],
        required=False,
        allow_blank=True,
        allow_null=True
    )
    mobile_money_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    ecoret_account_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ecoret_billing_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    virtual_account_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    virtual_account_holder = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    daily_transaction_limit = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        allow_null=True
    )
    max_loan_amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        allow_null=True
    )
    
    def validate_mobile_money_number(self, value):
        if value:
            import re
            if not re.match(r'^\+?[0-9]{10,15}$', value):
                raise serializers.ValidationError('Invalid phone number format. Use format: +265999123456')
        return value
    
    def validate_bank_account_number(self, value):
        if value:
            if len(value) < 10:
                raise serializers.ValidationError('Bank account number must be at least 10 digits')
        return value

class GroupSerializer(serializers.ModelSerializer):
    chairman_details = UserSerializer(source='chairman', read_only=True)
    secretary_details = UserSerializer(source='secretary', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = [
            'id', 'group_name', 'group_code', 'chairman', 'chairman_details',
            'secretary', 'secretary_details', 'treasurer', 
            'bank_account_number', 'address', 
            'profile_photo', 'is_active', 'activation_date', 
            'created_at', 'updated_at', 'member_count'
        ]
        read_only_fields = ['id', 'group_code', 'activation_date', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        return obj.get_member_count()

class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['group_name', 'address']
    
    def validate_group_name(self, value):
        if Group.objects.filter(group_name__iexact=value).exists():
            raise serializers.ValidationError('Group name already exists')
        return value

class GroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = [
            'group_name', 'address', 'bank_account_number', 
            'profile_photo'
        ]

class GroupMemberSerializer(serializers.ModelSerializer):
    attendance_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = GroupMember
        fields = [
            'id', 'full_name', 'national_id', 'national_id_photo',
            'business_type', 'business_description',
            'phone_number', 'gender', 'address', 'is_active', 
            'joined_date', 'updated_at', 'attendance_percentage'
        ]
        read_only_fields = ['id', 'joined_date', 'updated_at']
    
    def get_attendance_percentage(self, obj):
        return obj.get_attendance_percentage()

class GroupMemberCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMember
        fields = ['full_name', 'national_id', 'national_id_photo',
                 'phone_number', 'gender', 'address',
                 'business_type', 'business_description']
    
    def validate_phone_number(self, value):
        import re
        pattern = r'^\+?[0-9]{10,15}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError('Invalid phone number format. Use format: +265999123456')
        return value
    
    def validate_national_id(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Invalid National ID. Must be at least 5 characters.')
        return value

class GroupMemberUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMember
        fields = ['full_name', 'national_id', 'national_id_photo',
                 'phone_number', 'gender', 'address', 'is_active',
                 'business_type', 'business_description']

class GroupRecordSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = GroupRecord
        fields = [
            'id', 'record_name', 'record_type', 'file', 
            'uploaded_by', 'uploaded_by_name', 'description', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at']


class GroupRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupRecord
        fields = ['record_name', 'record_type', 'file', 'description']