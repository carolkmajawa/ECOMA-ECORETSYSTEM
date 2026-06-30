from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.contrib.auth import logout
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
import bcrypt
import uuid
import logging
from apps.accounts import serializers

from .models import User, UserDevice, PasswordResetToken, UserActivityLog
from .serializers import (
    UserSerializer, LoginSerializer, RegisterSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, UserDeviceSerializer, UserActivityLogSerializer
)

logger = logging.getLogger(__name__)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Reset login attempts on successful login
        user.login_attempts = 0
        user.account_locked = False
        user.lock_expiry = None
        user.last_login = timezone.now()
        user.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Log login activity
        UserActivityLog.objects.create(
            user=user,
            action='login',
            details={'ip': request.META.get('REMOTE_ADDR')},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        UserActivityLog.objects.create(
            user=user,
            action='register',
            details={'ip': request.META.get('REMOTE_ADDR')},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'message': 'User registered successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # Log logout
            UserActivityLog.objects.create(
                user=request.user,
                action='logout',
                details={'ip': request.META.get('REMOTE_ADDR')}
            )
            
            return Response({'message': 'Logged out successfully'})
        except Exception as e:
            logger.error(f'Logout error: {str(e)}')
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            raise serializers.ValidationError('Old password is incorrect')
        
        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        UserActivityLog.objects.create(
            user=user,
            action='change_password',
            details={'ip': request.META.get('REMOTE_ADDR')}
        )
        
        return Response({'message': 'Password changed successfully'})

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        user = User.objects.get(email=email)
        
        # Generate reset token
        token = uuid.uuid4().hex[:32]
        token_hash = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
        
        # Save token
        PasswordResetToken.objects.update_or_create(
            user=user,
            defaults={
                'token_hash': token_hash.decode('utf-8'),
                'expires_at': timezone.now() + timezone.timedelta(hours=1)
            }
        )
        
        # Send email
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        try:
            send_mail(
                'Password Reset - ECORET',
                f'Click the link to reset your password: {reset_link}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False
            )
        except Exception as e:
            logger.error(f'Failed to send password reset email: {str(e)}')
            return Response(
                {'error': 'Failed to send password reset email'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({'message': 'Password reset link sent to your email'})

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        # Find valid token
        reset_tokens = PasswordResetToken.objects.filter(
            expires_at__gt=timezone.now()
        )
        
        valid_token = None
        for reset in reset_tokens:
            if bcrypt.checkpw(token.encode('utf-8'), reset.token_hash.encode('utf-8')):
                valid_token = reset
                break
        
        if not valid_token:
            raise serializers.ValidationError('Invalid or expired token')
        
        # Update password
        user = valid_token.user
        user.set_password(new_password)
        user.save()
        
        # Delete token
        valid_token.delete()
        
        UserActivityLog.objects.create(
            user=user,
            action='reset_password',
            details={'ip': request.META.get('REMOTE_ADDR')}
        )
        
        return Response({'message': 'Password reset successfully'})

class UserProfileView(APIView):
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action='update_profile',
            details={'ip': request.META.get('REMOTE_ADDR')}
        )
        
        return Response(serializer.data)

class UserDeviceRegisterView(APIView):
    def post(self, request):
        serializer = UserDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if device already exists
        device, created = UserDevice.objects.update_or_create(
            user=request.user,
            device_id=serializer.validated_data['device_id'],
            defaults={
                'fcm_token': serializer.validated_data['fcm_token'],
                'device_type': serializer.validated_data['device_type'],
                'is_active': True
            }
        )
        
        return Response(UserDeviceSerializer(device).data)

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']

class UserActivityLogView(generics.ListAPIView):
    serializer_class = UserActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return UserActivityLog.objects.all()
        return UserActivityLog.objects.filter(user=self.request.user)

class CheckAuthView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response({
            'authenticated': True,
            'user': UserSerializer(request.user).data
        })