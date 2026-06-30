from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserDevice, UserActivityLog
from django.utils import timezone

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 
                 'phone_number', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(request=self.context.get('request'), 
                              email=email, password=password)
            
            if not user:
                # Check if user exists but is locked
                try:
                    user_exists = User.objects.get(email=email)
                    if user_exists.account_locked:
                        raise serializers.ValidationError(
                            'Account is locked. Please try again later or reset your password.'
                        )
                except User.DoesNotExist:
                    pass
                raise serializers.ValidationError('Invalid credentials')
            
            if not user.is_active:
                raise serializers.ValidationError('Account is disabled')
            
            if user.account_locked:
                if user.lock_expiry and user.lock_expiry > timezone.now():
                    minutes_left = (user.lock_expiry - timezone.now()).seconds // 60
                    raise serializers.ValidationError(
                        f'Account is locked. Try again in {minutes_left} minutes.'
                    )
                else:
                    # Auto-unlock if lock expired
                    user.account_locked = False
                    user.login_attempts = 0
                    user.save()
        else:
            raise serializers.ValidationError('Email and password are required')
        
        data['user'] = user
        return data

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 
                 'password', 'confirm_password', 'role']
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        
        # Check if email already exists
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already registered'})
        
        # Check if phone number already exists
        if User.objects.filter(phone_number=data['phone_number']).exists():
            raise serializers.ValidationError({'phone_number': 'Phone number already registered'})
        
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        return data

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError('User with this email does not exist')
        return value

class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match'})
        return data

class UserDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = ['id', 'device_id', 'fcm_token', 'device_type', 'is_active']

class UserActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = UserActivityLog
        fields = ['id', 'user', 'user_name', 'action', 'details', 'ip_address', 'created_at']