from django.contrib import admin
from .models import Group, GroupMember, GroupRecord

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['group_name', 'group_code', 'chairman', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_cycle_active']
    search_fields = ['group_name', 'group_code']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('group_name', 'group_code', 'address', 'profile_photo')
        }),
        ('Leadership', {
            'fields': ('chairman', 'secretary', 'treasurer')
        }),
        ('Interest Rates', {
            'fields': ('default_interest_rate',)
        }),
        ('Policy Settings', {
            'fields': ('social_max_contribution', 'savings_max_contribution', 'savings_min_contribution')
        }),
        ('Cycle Management', {
            'fields': ('cycle_start_date', 'cycle_end_date', 'cycle_duration_months', 'is_cycle_active')
        }),
        ('Meeting Settings', {
            'fields': ('meeting_frequency', 'meeting_day')
        }),
        ('Bank Account', {
            'fields': ('bank_name', 'bank_account_number', 'billing_number', 'bank_account_name', 'bank_branch')
        }),
        ('Mobile Money', {
            'fields': ('mobile_money_provider', 'mobile_money_number')
        }),
        ('ECORET Account', {
            'fields': ('ecoret_account_id', 'ecoret_billing_code', 'virtual_account_number', 'virtual_account_holder')
        }),
        ('Limits', {
            'fields': ('daily_transaction_limit', 'max_loan_amount')
        }),
        ('Status', {
            'fields': ('is_active', 'activation_date')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'group', 'phone_number', 'business_type', 'is_active']
    list_filter = ['group', 'gender', 'business_type', 'is_active']
    search_fields = ['full_name', 'phone_number', 'national_id', 'business_description']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('full_name', 'national_id', 'national_id_photo', 'phone_number', 'gender', 'address')
        }),
        ('Business Information', {
            'fields': ('business_type', 'business_description')
        }),
        ('Group Information', {
            'fields': ('group', 'user')
        }),
        ('Status', {
            'fields': ('is_active', 'joined_date', 'updated_at')
        })
    )
    readonly_fields = ['joined_date', 'updated_at']

@admin.register(GroupRecord)
class GroupRecordAdmin(admin.ModelAdmin):
    list_display = ['record_name', 'record_type', 'group', 'uploaded_by']
    list_filter = ['record_type', 'group']
    search_fields = ['record_name', 'description']