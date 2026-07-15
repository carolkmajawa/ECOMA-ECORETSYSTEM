from django.contrib import admin
from .models import USSDRequest, USSDOTP, USSDLoanRequest, USSDSession

@admin.register(USSDRequest)
class USSDRequestAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'session_id', 'created_at']  # Removed 'status'
    list_filter = ['created_at']  # Removed 'status'
    search_fields = ['phone_number', 'session_id']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(USSDOTP)
class USSDOTPAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'otp_code', 'purpose', 'is_used', 'expires_at']
    list_filter = ['purpose', 'is_used']
    search_fields = ['phone_number', 'otp_code']

@admin.register(USSDLoanRequest)
class USSDLoanRequestAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['member__full_name']

@admin.register(USSDSession)
class USSDSessionAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'session_id', 'language', 'current_menu', 'is_active']
    list_filter = ['language', 'is_active']
    search_fields = ['phone_number', 'session_id']