from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserDevice, UserActivityLog

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'account_locked']
    list_filter = ['role', 'is_active', 'account_locked']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering = ['email']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number', 'role')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Security'), {'fields': ('login_attempts', 'account_locked', 'lock_expiry')}),
        (_('Important dates'), {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    readonly_fields = ['created_at', 'updated_at']

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_id', 'device_type', 'is_active', 'created_at']
    list_filter = ['device_type', 'is_active']
    search_fields = ['user__email', 'device_id']

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'ip_address', 'created_at']
    list_filter = ['action']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at']