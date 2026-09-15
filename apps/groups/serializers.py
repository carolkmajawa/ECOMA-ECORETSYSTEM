# # from rest_framework import serializers
# # from .models import Group, GroupMember, GroupRecord
# # from apps.accounts.serializers import UserSerializer

# # class GroupBankAccountSerializer(serializers.ModelSerializer):
# #     """Serializer for group bank account details"""
    
# #     class Meta:
# #         model = Group
# #         fields = [
# #             'bank_name',
# #             'bank_account_number',
# #             'bank_account_name',
# #             'bank_branch',
# #             'mobile_money_provider',
# #             'mobile_money_number',
# #             'ecoret_account_id',
# #             'ecoret_billing_code',
# #             'virtual_account_number',
# #             'virtual_account_holder',
# #             'daily_transaction_limit',
# #             'max_loan_amount'
# #         ]

# # class GroupBankAccountUpdateSerializer(serializers.Serializer):
# #     """Serializer for updating bank account details"""
    
# #     bank_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
# #     bank_account_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
# #     bank_account_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
# #     bank_branch = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
# #     mobile_money_provider = serializers.ChoiceField(
# #         choices=['mpamba', 'airtel_money', 'tnm_mpamba', 'other'],
# #         required=False,
# #         allow_blank=True,
# #         allow_null=True
# #     )
# #     mobile_money_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
# #     ecoret_account_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
# #     ecoret_billing_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
# #     virtual_account_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
# #     virtual_account_holder = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
# #     daily_transaction_limit = serializers.DecimalField(
# #         max_digits=10, 
# #         decimal_places=2, 
# #         required=False,
# #         allow_null=True
# #     )
# #     max_loan_amount = serializers.DecimalField(
# #         max_digits=10, 
# #         decimal_places=2, 
# #         required=False,
# #         allow_null=True
# #     )
    
# #     def validate_mobile_money_number(self, value):
# #         if value:
# #             import re
# #             if not re.match(r'^\+?[0-9]{10,15}$', value):
# #                 raise serializers.ValidationError('Invalid phone number format. Use format: +265999123456')
# #         return value
    
# #     def validate_bank_account_number(self, value):
# #         if value:
# #             if len(value) < 10:
# #                 raise serializers.ValidationError('Bank account number must be at least 10 digits')
# #         return value

# # class GroupSerializer(serializers.ModelSerializer):
# #     chairman_details = UserSerializer(source='chairman', read_only=True)
# #     secretary_details = UserSerializer(source='secretary', read_only=True)
# #     member_count = serializers.SerializerMethodField()
    
# #     class Meta:
# #         model = Group
# #         fields = [
# #             'id', 'group_name', 'group_code', 'chairman', 'chairman_details',
# #             'secretary', 'secretary_details', 'treasurer', 
# #             'bank_account_number', 'address', 
# #             'profile_photo', 'is_active', 'activation_date', 
# #             'created_at', 'updated_at', 'member_count'
# #         ]
# #         read_only_fields = ['id', 'group_code', 'activation_date', 'created_at', 'updated_at']
    
# #     def get_member_count(self, obj):
# #         return obj.get_member_count()

# # class GroupCreateSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = Group
# #         fields = ['group_name', 'address']
    
# #     def validate_group_name(self, value):
# #         if Group.objects.filter(group_name__iexact=value).exists():
# #             raise serializers.ValidationError('Group name already exists')
# #         return value

# # class GroupUpdateSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = Group
# #         fields = [
# #             'group_name', 'address', 'bank_account_number', 
# #             'profile_photo'
# #         ]

# # class GroupMemberSerializer(serializers.ModelSerializer):
# #     attendance_percentage = serializers.SerializerMethodField()
    
# #     class Meta:
# #         model = GroupMember
# #         fields = [
# #             'id', 'full_name', 'national_id', 'national_id_photo',
# #             'business_type', 'business_description',
# #             'phone_number', 'gender', 'address', 'is_active', 
# #             'joined_date', 'updated_at', 'attendance_percentage'
# #         ]
# #         read_only_fields = ['id', 'joined_date', 'updated_at']
    
# #     def get_attendance_percentage(self, obj):
# #         return obj.get_attendance_percentage()

# # class GroupMemberCreateSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = GroupMember
# #         fields = ['full_name', 'national_id', 'national_id_photo',
# #                  'phone_number', 'gender', 'address',
# #                  'business_type', 'business_description']
    
# #     def validate_phone_number(self, value):
# #         import re
# #         pattern = r'^\+?[0-9]{10,15}$'
# #         if not re.match(pattern, value):
# #             raise serializers.ValidationError('Invalid phone number format. Use format: +265999123456')
# #         return value
    
# #     def validate_national_id(self, value):
# #         if not value or len(value) < 5:
# #             raise serializers.ValidationError('Invalid National ID. Must be at least 5 characters.')
# #         return value

# # class GroupMemberUpdateSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = GroupMember
# #         fields = ['full_name', 'national_id', 'national_id_photo',
# #                  'phone_number', 'gender', 'address', 'is_active',
# #                  'business_type', 'business_description']

# # class GroupRecordSerializer(serializers.ModelSerializer):
# #     uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
# #     class Meta:
# #         model = GroupRecord
# #         fields = [
# #             'id', 'record_name', 'record_type', 'file', 
# #             'uploaded_by', 'uploaded_by_name', 'description', 'uploaded_at'
# #         ]
# #         read_only_fields = ['id', 'uploaded_at']


# # class GroupRecordCreateSerializer(serializers.ModelSerializer):
# #     class Meta:
# #         model = GroupRecord
# #         fields = ['record_name', 'record_type', 'file', 'description']



# # apps/groups/serializers.py - FINAL CORRECTED
# from rest_framework import serializers
# from .models import Group, GroupMember, GroupRecord
# from apps.accounts.serializers import UserSerializer


# class GroupBankAccountSerializer(serializers.ModelSerializer):
#     """Serializer for group bank account details"""
    
#     class Meta:
#         model = Group
#         fields = [
#             'bank_name',
#             'bank_account_number',
#             'bank_account_name',
#             'bank_branch',
#             'mobile_money_provider',
#             'mobile_money_number',
#             'ecoret_account_id',
#             'ecoret_billing_code',
#             'virtual_account_number',
#             'virtual_account_holder',
#             'daily_transaction_limit',
#             'max_loan_amount'
#         ]


# class GroupBankAccountUpdateSerializer(serializers.Serializer):
#     """Serializer for updating bank account details"""
    
#     bank_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     bank_account_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     bank_account_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     bank_branch = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
#     mobile_money_provider = serializers.ChoiceField(
#         choices=['mpamba', 'airtel_money', 'tnm_mpamba', 'other'],
#         required=False,
#         allow_blank=True,
#         allow_null=True
#     )
#     mobile_money_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
#     ecoret_account_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     ecoret_billing_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
#     virtual_account_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
#     virtual_account_holder = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
#     daily_transaction_limit = serializers.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         required=False,
#         allow_null=True
#     )
#     max_loan_amount = serializers.DecimalField(
#         max_digits=10, 
#         decimal_places=2, 
#         required=False,
#         allow_null=True
#     )
    
#     def validate_mobile_money_number(self, value):
#         if value:
#             import re
#             if not re.match(r'^\+?[0-9]{10,15}$', value):
#                 raise serializers.ValidationError('Invalid phone number format. Use format: +265999123456')
#         return value
    
#     def validate_bank_account_number(self, value):
#         if value:
#             if len(value) < 10:
#                 raise serializers.ValidationError('Bank account number must be at least 10 digits')
#         return value


# class GroupSerializer(serializers.ModelSerializer):
#     chairman_details = UserSerializer(source='chairman', read_only=True)
#     secretary_details = UserSerializer(source='secretary', read_only=True)
#     treasurer_details = UserSerializer(source='treasurer', read_only=True)
#     member_count = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Group
#         fields = [
#             'id', 'group_name', 'group_code', 'chairman', 'chairman_details',
#             'secretary', 'secretary_details', 'treasurer', 'treasurer_details',
#             'bank_account_number', 'address', 
#             'profile_photo', 'is_active', 'activation_date', 
#             'created_at', 'updated_at', 'member_count',
#             # Loan settings - ONLY fields that exist in your model
#             'default_interest_rate',
#             'max_loan_amount',  # This is the max loan amount
#             # Contribution settings
#             'social_max_contribution',
#             'savings_min_contribution',
#             'savings_max_contribution',
#             # Meeting settings
#             'meeting_frequency',
#             'meeting_day',
#             # Limits
#             'daily_transaction_limit',
#             'max_loan_amount',
#             # Cycle fields
#             'cycle_start_date',
#             'cycle_end_date',
#             'cycle_duration_months',
#             'is_cycle_active'
#         ]
#         read_only_fields = ['id', 'group_code', 'activation_date', 'created_at', 'updated_at']

#     def get_member_count(self, obj):
#         return obj.get_member_count()


# class GroupCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Group
#         fields = ['group_name', 'address']
    
#     def validate_group_name(self, value):
#         if Group.objects.filter(group_name__iexact=value).exists():
#             raise serializers.ValidationError('Group name already exists')
#         return value


# class GroupUpdateSerializer(serializers.ModelSerializer):
#     """Serializer for updating group settings"""
    
#     class Meta:
#         model = Group
#         fields = [
#             # Basic info
#             'group_name', 
#             'address', 
#             'bank_account_number', 
#             'profile_photo',
#             # Loan settings - ONLY fields that exist
#             'default_interest_rate',
#             'max_loan_amount',  # This is the max loan amount
#             # Contribution settings
#             'social_max_contribution',
#             'savings_min_contribution',
#             'savings_max_contribution',
#             # Meeting settings
#             'meeting_frequency',
#             'meeting_day',
#             # Limits
#             'daily_transaction_limit',
#             'max_loan_amount'
#         ]
#         # All fields are optional for partial updates
#         extra_kwargs = {
#             'group_name': {'required': False},
#             'address': {'required': False},
#             'bank_account_number': {'required': False},
#             'profile_photo': {'required': False},
#             'default_interest_rate': {'required': False, 'allow_null': True},
#             'max_loan_amount': {'required': False, 'allow_null': True},
#             'social_max_contribution': {'required': False, 'allow_null': True},
#             'savings_min_contribution': {'required': False, 'allow_null': True},
#             'savings_max_contribution': {'required': False, 'allow_null': True},
#             'meeting_frequency': {'required': False, 'allow_null': True},
#             'meeting_day': {'required': False, 'allow_null': True},
#             'daily_transaction_limit': {'required': False, 'allow_null': True},
#         }
    
#     def validate_default_interest_rate(self, value):
#         if value is not None and (value < 0 or value > 100):
#             raise serializers.ValidationError('Interest rate must be between 0 and 100')
#         return value
    
#     def validate_max_loan_amount(self, value):
#         if value is not None and value < 0:
#             raise serializers.ValidationError('Maximum loan amount cannot be negative')
#         return value


# class GroupMemberSerializer(serializers.ModelSerializer):
#     attendance_percentage = serializers.SerializerMethodField()
    
#     class Meta:
#         model = GroupMember
#         fields = [
#             'id', 'full_name', 'national_id', 'national_id_photo',
#             'business_type', 'business_description',
#             'phone_number', 'gender', 'address', 'is_active', 
#             'joined_date', 'updated_at', 'attendance_percentage',
#             'bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch',
#             'mobile_money_provider', 'mobile_money_number'
#         ]
#         read_only_fields = ['id', 'joined_date', 'updated_at']
    
#     def get_attendance_percentage(self, obj):
#         return obj.get_attendance_percentage()


# class GroupMemberCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = GroupMember
#         fields = [
#             'full_name', 'national_id', 'national_id_photo',
#             'phone_number', 'gender', 'address',
#             'business_type', 'business_description'
#         ]
    
#     def validate_phone_number(self, value):
#         import re
#         pattern = r'^\+?[0-9]{10,15}$'
#         if not re.match(pattern, value):
#             raise serializers.ValidationError('Invalid phone number format. Use format: +265999123456')
#         return value
    
#     def validate_national_id(self, value):
#         if not value or len(value) < 5:
#             raise serializers.ValidationError('Invalid National ID. Must be at least 5 characters.')
#         return value


# class GroupMemberUpdateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = GroupMember
#         fields = [
#             'full_name', 'national_id', 'national_id_photo',
#             'phone_number', 'gender', 'address', 'is_active',
#             'business_type', 'business_description',
#             'bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch',
#             'mobile_money_provider', 'mobile_money_number'
#         ]


# class GroupRecordSerializer(serializers.ModelSerializer):
#     uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
#     class Meta:
#         model = GroupRecord
#         fields = [
#             'id', 'record_name', 'record_type', 'file', 
#             'uploaded_by', 'uploaded_by_name', 'description', 'uploaded_at'
#         ]
#         read_only_fields = ['id', 'uploaded_at']


# class GroupRecordCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = GroupRecord
#         fields = ['record_name', 'record_type', 'file', 'description']



# apps/groups/serializers.py - FIXED

from rest_framework import serializers
from .models import Group, GroupMember, GroupRecord, LedgerEntry, LedgerCategory
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


class GroupMemberSerializer(serializers.ModelSerializer):
    attendance_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = GroupMember
        fields = [
            'id', 'full_name', 'national_id', 'national_id_photo',
            'business_type', 'business_description',
            'phone_number', 'gender', 'address', 'is_active', 
            'joined_date', 'updated_at', 'attendance_percentage',
            'bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch',
            'mobile_money_provider', 'mobile_money_number'
        ]
        read_only_fields = ['id', 'joined_date', 'updated_at']
    
    def get_attendance_percentage(self, obj):
        return obj.get_attendance_percentage()


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Group - FIXED"""
    chairman_details = UserSerializer(source='chairman', read_only=True)
    secretary_details = GroupMemberSerializer(source='secretary', read_only=True)
    treasurer_details = GroupMemberSerializer(source='treasurer', read_only=True)
    member_count = serializers.SerializerMethodField()
    chairman_name = serializers.CharField(source='chairman.get_full_name', read_only=True)
    
    class Meta:
        model = Group
        fields = [
            'id', 
            'group_name', 
            'group_code', 
            'address',
            'chairman', 
            'chairman_name',           # ✅ Added
            'chairman_details',        # ✅ Added
            'secretary', 
            'secretary_details',       # ✅ Added
            'treasurer', 
            'treasurer_details',       # ✅ Added
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
            'profile_photo', 
            'is_active', 
            'activation_date', 
            'created_at', 
            'updated_at', 
            'member_count',
            # Loan settings
            'default_interest_rate',
            'max_loan_amount',
            # Contribution settings
            'social_max_contribution',
            'savings_min_contribution',
            'savings_max_contribution',
            # Meeting settings
            'meeting_frequency',
            'meeting_day',
            # Limits
            'daily_transaction_limit',
            # Cycle fields
            'cycle_start_date',
            'cycle_end_date',
            'cycle_duration_months',
            'is_cycle_active'
        ]
        read_only_fields = [
            'id', 'group_code', 'activation_date', 'created_at', 
            'updated_at', 'member_count', 'chairman_name'
        ]

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
    """Serializer for updating group settings"""
    
    class Meta:
        model = Group
        fields = [
            'group_name', 
            'address', 
            'bank_account_number', 
            'profile_photo',
            'default_interest_rate',
            'max_loan_amount',
            'social_max_contribution',
            'savings_min_contribution',
            'savings_max_contribution',
            'meeting_frequency',
            'meeting_day',
            'daily_transaction_limit',
            'secretary',
            'treasurer'
        ]
        extra_kwargs = {
            'group_name': {'required': False},
            'address': {'required': False},
            'bank_account_number': {'required': False},
            'profile_photo': {'required': False},
            'default_interest_rate': {'required': False, 'allow_null': True},
            'max_loan_amount': {'required': False, 'allow_null': True},
            'social_max_contribution': {'required': False, 'allow_null': True},
            'savings_min_contribution': {'required': False, 'allow_null': True},
            'savings_max_contribution': {'required': False, 'allow_null': True},
            'meeting_frequency': {'required': False, 'allow_null': True},
            'meeting_day': {'required': False, 'allow_null': True},
            'daily_transaction_limit': {'required': False, 'allow_null': True},
            'secretary': {'required': False, 'allow_null': True},
            'treasurer': {'required': False, 'allow_null': True},
        }
    
    def validate_default_interest_rate(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError('Interest rate must be between 0 and 100')
        return value
    
    def validate_max_loan_amount(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Maximum loan amount cannot be negative')
        return value


class GroupMemberCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupMember
        fields = [
            'full_name', 'national_id', 'national_id_photo',
            'phone_number', 'gender', 'address',
            'business_type', 'business_description'
        ]
    
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
        fields = [
            'full_name', 'national_id', 'national_id_photo',
            'phone_number', 'gender', 'address', 'is_active',
            'business_type', 'business_description',
            'bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch',
            'mobile_money_provider', 'mobile_money_number'
        ]


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


# ==================== LEDGER SERIALIZERS ====================

class LedgerEntrySerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    member_phone = serializers.CharField(source='member.phone_number', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    is_auto_generated = serializers.BooleanField(read_only=True)
    source_model = serializers.CharField(read_only=True)
    
    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'group', 'transaction_type', 'transaction_type_display',
            'category', 'category_display', 'amount', 'balance',
            'member', 'member_name', 'member_phone',
            'loan', 'description', 'reference_number',
            'recorded_by', 'recorded_by_name', 'recorded_at',
            'updated_at', 'is_verified', 'verified_by',
            'verified_at', 'is_deleted','is_auto_generated', 'source_model'
        ]
        read_only_fields = [
            'id', 'balance', 'recorded_at', 'updated_at',
            'recorded_by', 'recorded_by_name',
            'is_auto_generated', 'source_model'
        ]


class LedgerEntryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            'transaction_type', 'category', 'amount',
            'member', 'loan', 'description', 'reference_number'
        ]
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero")
        return value
    
    def validate(self, data):
        if data.get('member') and data.get('group'):
            if data['member'].group != data['group']:
                raise serializers.ValidationError("Member does not belong to this group")
        return data


class LedgerCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerCategory
        fields = [
            'id', 'group', 'name', 'description',
            'color', 'icon', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LedgerSummarySerializer(serializers.Serializer):
    """Serializer for ledger summary"""
    total_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_income = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_expenses = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_savings = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_loans_disbursed = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_loans_repaid = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_social_fund = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_fines = serializers.DecimalField(max_digits=10, decimal_places=2)
    member_count = serializers.IntegerField()
    transaction_count = serializers.IntegerField()