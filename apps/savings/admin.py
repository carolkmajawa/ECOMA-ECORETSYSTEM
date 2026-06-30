from django.contrib import admin
from .models import Saving, SavingGoal, SavingSummary

@admin.register(Saving)
class SavingAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'transaction_type', 'transaction_date']
    list_filter = ['transaction_type', 'saving_type']
    search_fields = ['member__full_name', 'reference_number']

@admin.register(SavingGoal)
class SavingGoalAdmin(admin.ModelAdmin):
    list_display = ['name', 'group', 'target_amount', 'current_amount', 'is_completed']
    list_filter = ['is_completed']
    search_fields = ['name']

@admin.register(SavingSummary)
class SavingSummaryAdmin(admin.ModelAdmin):
    list_display = ['group', 'date', 'total_deposits', 'total_withdrawals']
    list_filter = ['date']
    search_fields = ['group__group_name']