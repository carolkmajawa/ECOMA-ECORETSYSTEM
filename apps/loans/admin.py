from django.contrib import admin
from .models import Loan, LoanRepayment, LoanRequest, LoanSettings, ECORETSettings

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'status', 'loan_type', 'due_date']
    list_filter = ['status', 'loan_type']
    search_fields = ['member__full_name', 'purpose']
    readonly_fields = ['id', 'request_date', 'created_at', 'updated_at']

@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ['loan', 'amount', 'payment_date', 'payment_method']
    list_filter = ['payment_method']
    search_fields = ['loan__member__full_name', 'transaction_reference']

@admin.register(LoanRequest)
class LoanRequestAdmin(admin.ModelAdmin):
    list_display = ['group', 'amount', 'status', 'request_date']
    list_filter = ['status']
    search_fields = ['group__group_name', 'purpose']

# ✅ UPDATED: LoanSettingsAdmin with new dynamic fields
@admin.register(LoanSettings)
class LoanSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'group',
        'group_loan_interest_rate',
        'group_loan_duration_months',
        'ecoret_loan_interest_rate',
        'ecoret_loan_duration_months'
    ]
    list_filter = ['group']
    search_fields = ['group__group_name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('🏦 Group Loan Settings (Set by Chairman)', {
            'fields': (
                'group_loan_interest_rate',
                'group_loan_duration_months',
                'group_loan_min_amount',
                'group_loan_max_amount'
            )
        }),
        ('🌐 ECORET Loan Settings (Set by ECORET Admin)', {
            'fields': (
                'ecoret_loan_interest_rate',
                'ecoret_loan_duration_months',
                'ecoret_loan_min_amount',
                'ecoret_loan_max_amount'
            )
        }),
        ('⚙️ General Settings', {
            'fields': (
                'requires_guarantor',
                'min_guarantors',
                'grace_period_days',
                'late_fee_percentage'
            )
        }),
        ('📅 Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

# ✅ NEW: ECORETSettings Admin
@admin.register(ECORETSettings)
class ECORETSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'ecoret_loan_interest_rate',
        'ecoret_loan_duration_months',
        'ecoret_loan_max_amount',
        'service_fee_percentage',
        'updated_at'
    ]
    
    fieldsets = (
        ('📊 ECORET Loan Rates', {
            'fields': (
                'ecoret_loan_interest_rate',
                'ecoret_loan_duration_months',
                'ecoret_loan_min_amount',
                'ecoret_loan_max_amount'
            )
        }),
        ('💰 ECORET Service Fees', {
            'fields': ('service_fee_percentage',)
        }),
        ('📝 Audit', {
            'fields': ('updated_by', 'updated_at')
        })
    )
    readonly_fields = ['updated_at']
    
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)