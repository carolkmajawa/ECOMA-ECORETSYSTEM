# from rest_framework import status, generics, permissions
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from rest_framework_simplejwt.tokens import RefreshToken
# from django.utils import timezone
# from django.contrib.auth import logout
# from django.core.mail import send_mail
# from django.conf import settings
# from django.contrib.auth.password_validation import validate_password
# import bcrypt
# import uuid
# import logging
# from apps.accounts import serializers

# from .models import User, UserDevice, PasswordResetToken, UserActivityLog
# from .serializers import (
#     UserSerializer, LoginSerializer, RegisterSerializer,
#     ChangePasswordSerializer, ForgotPasswordSerializer,
#     ResetPasswordSerializer, UserDeviceSerializer, UserActivityLogSerializer
# )

# logger = logging.getLogger(__name__)

# class LoginView(APIView):
#     permission_classes = [permissions.AllowAny]
    
#     def post(self, request):
#         serializer = LoginSerializer(data=request.data, context={'request': request})
#         serializer.is_valid(raise_exception=True)
        
#         user = serializer.validated_data['user']
        
#         # Reset login attempts on successful login
#         user.login_attempts = 0
#         user.account_locked = False
#         user.lock_expiry = None
#         user.last_login = timezone.now()
#         user.save()
        
#         # Generate JWT tokens
#         refresh = RefreshToken.for_user(user)
        
#         # Log login activity
#         UserActivityLog.objects.create(
#             user=user,
#             action='login',
#             details={'ip': request.META.get('REMOTE_ADDR')},
#             ip_address=request.META.get('REMOTE_ADDR'),
#             user_agent=request.META.get('HTTP_USER_AGENT', '')
#         )
        
#         return Response({
#             'refresh': str(refresh),
#             'access': str(refresh.access_token),
#             'user': UserSerializer(user).data
#         })

# class RegisterView(generics.CreateAPIView):
#     queryset = User.objects.all()
#     serializer_class = RegisterSerializer
#     permission_classes = [permissions.AllowAny]
    
#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         user = serializer.save()
        
#         UserActivityLog.objects.create(
#             user=user,
#             action='register',
#             details={'ip': request.META.get('REMOTE_ADDR')},
#             ip_address=request.META.get('REMOTE_ADDR')
#         )
        
#         return Response({
#             'message': 'User registered successfully',
#             'user': UserSerializer(user).data
#         }, status=status.HTTP_201_CREATED)

# class LogoutView(APIView):
#     def post(self, request):
#         try:
#             refresh_token = request.data.get('refresh')
#             if refresh_token:
#                 token = RefreshToken(refresh_token)
#                 token.blacklist()
            
#             # Log logout
#             UserActivityLog.objects.create(
#                 user=request.user,
#                 action='logout',
#                 details={'ip': request.META.get('REMOTE_ADDR')}
#             )
            
#             return Response({'message': 'Logged out successfully'})
#         except Exception as e:
#             logger.error(f'Logout error: {str(e)}')
#             return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# class ChangePasswordView(APIView):
#     def post(self, request):
#         serializer = ChangePasswordSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         user = request.user
        
#         # Check old password
#         if not user.check_password(serializer.validated_data['old_password']):
#             raise serializers.ValidationError('Old password is incorrect')
        
#         # Set new password
#         user.set_password(serializer.validated_data['new_password'])
#         user.save()
        
#         UserActivityLog.objects.create(
#             user=user,
#             action='change_password',
#             details={'ip': request.META.get('REMOTE_ADDR')}
#         )
        
#         return Response({'message': 'Password changed successfully'})

# # apps/accounts/views.py
# import logging
# import uuid
# import bcrypt
# from django.core.mail import send_mail
# from django.conf import settings
# from django.utils import timezone
# from rest_framework import status, permissions
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from django.template.loader import render_to_string
# from django.utils.html import strip_tags
# from django.core.mail import EmailMultiAlternatives

# logger = logging.getLogger(__name__)

# class ForgotPasswordView(APIView):
#     permission_classes = [permissions.AllowAny]
    
#     def post(self, request):
#         serializer = ForgotPasswordSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         email = serializer.validated_data['email']
        
#         try:
#             user = User.objects.get(email=email)
#         except User.DoesNotExist:
#             # Security: Don't reveal if user exists or not
#             return Response({
#                 'message': 'If an account exists with this email, a password reset link has been sent.'
#             })
        
#         # Generate reset token
#         token = uuid.uuid4().hex[:32]
#         token_hash = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
        
#         # Save token
#         PasswordResetToken.objects.update_or_create(
#             user=user,
#             defaults={
#                 'token_hash': token_hash.decode('utf-8'),
#                 'expires_at': timezone.now() + timezone.timedelta(hours=1)
#             }
#         )
        
#         # Send email
#         try:
#             self.send_reset_email(user, token)
#             return Response({'message': 'Password reset link sent to your email'})
#         except Exception as e:
#             logger.error(f'Failed to send password reset email to {email}: {str(e)}')
#             # Return more specific error for debugging
#             return Response(
#                 {
#                     'error': 'Failed to send password reset email. Please try again later.',
#                     'details': str(e) if settings.DEBUG else None
#                 },
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
    
#     def send_reset_email(self, user, token):
#         """Send password reset email with HTML template"""
#         reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        
#         # HTML email template
#         html_content = f"""
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <style>
#                 body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
#                 .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
#                 .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
#                 .content {{ padding: 20px; background: #f9f9f9; }}
#                 .button {{ 
#                     display: inline-block; 
#                     padding: 12px 24px; 
#                     background: #4CAF50; 
#                     color: white; 
#                     text-decoration: none; 
#                     border-radius: 5px;
#                     margin: 20px 0;
#                 }}
#                 .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
#                 .warning {{ color: #f44336; font-weight: bold; }}
#             </style>
#         </head>
#         <body>
#             <div class="container">
#                 <div class="header">
#                     <h1>ECORET Password Reset</h1>
#                 </div>
#                 <div class="content">
#                     <h2>Hello {user.first_name or user.email},</h2>
#                     <p>We received a request to reset your password for your ECORET account.</p>
#                     <p>Click the button below to reset your password:</p>
#                     <p style="text-align: center;">
#                         <a href="{reset_link}" class="button">Reset Password</a>
#                     </p>
#                     <p>Or copy and paste this link in your browser:</p>
#                     <p><a href="{reset_link}">{reset_link}</a></p>
#                     <p class="warning">This link will expire in 1 hour.</p>
#                     <p>If you didn't request a password reset, please ignore this email or contact support.</p>
#                     <hr>
#                     <p><strong>Security Tip:</strong> Never share your password with anyone.</p>
#                 </div>
#                 <div class="footer">
#                     <p>&copy; 2026 ECORET. All rights reserved.</p>
#                     <p>This is an automated message, please do not reply.</p>
#                 </div>
#             </div>
#         </body>
#         </html>
#         """
        
#         # Plain text version
#         text_content = f"""
#         ECORET Password Reset
        
#         Hello {user.first_name or user.email},
        
#         We received a request to reset your password for your ECORET account.
        
#         Click the link below to reset your password:
#         {reset_link}
        
#         This link will expire in 1 hour.
        
#         If you didn't request a password reset, please ignore this email.
        
#         Security Tip: Never share your password with anyone.
        
#         © 2026 ECORET. All rights reserved.
#         """
        
#         try:
#             # Try sending with HTML template first
#             email = EmailMultiAlternatives(
#                 subject='Password Reset - ECORET',
#                 body=text_content,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=[user.email],
#                 reply_to=['support@ecoret.com']
#             )
#             email.attach_alternative(html_content, "text/html")
#             email.send(fail_silently=False)
#             logger.info(f"Password reset email sent successfully to {user.email}")
#         except Exception as e:
#             logger.error(f"Failed to send HTML email: {str(e)}")
#             # Fallback to plain text email
#             send_mail(
#                 subject='Password Reset - ECORET',
#                 message=f'Click the link to reset your password: {reset_link}',
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 recipient_list=[user.email],
#                 fail_silently=False
#             )
# class ResetPasswordView(APIView):
#     permission_classes = [permissions.AllowAny]
    
#     def post(self, request):
#         serializer = ResetPasswordSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         token = serializer.validated_data['token']
#         new_password = serializer.validated_data['new_password']
        
#         # Find valid token
#         reset_tokens = PasswordResetToken.objects.filter(
#             expires_at__gt=timezone.now()
#         )
        
#         valid_token = None
#         for reset in reset_tokens:
#             if bcrypt.checkpw(token.encode('utf-8'), reset.token_hash.encode('utf-8')):
#                 valid_token = reset
#                 break
        
#         if not valid_token:
#             raise serializers.ValidationError('Invalid or expired token')
        
#         # Update password
#         user = valid_token.user
#         user.set_password(new_password)
#         user.save()
        
#         # Delete token
#         valid_token.delete()
        
#         UserActivityLog.objects.create(
#             user=user,
#             action='reset_password',
#             details={'ip': request.META.get('REMOTE_ADDR')}
#         )
        
#         return Response({'message': 'Password reset successfully'})

# class UserProfileView(APIView):
#     def get(self, request):
#         serializer = UserSerializer(request.user)
#         return Response(serializer.data)
    
#     def put(self, request):
#         serializer = UserSerializer(request.user, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
        
#         UserActivityLog.objects.create(
#             user=request.user,
#             action='update_profile',
#             details={'ip': request.META.get('REMOTE_ADDR')}
#         )
        
#         return Response(serializer.data)

# class UserDeviceRegisterView(APIView):
#     def post(self, request):
#         serializer = UserDeviceSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         # Check if device already exists
#         device, created = UserDevice.objects.update_or_create(
#             user=request.user,
#             device_id=serializer.validated_data['device_id'],
#             defaults={
#                 'fcm_token': serializer.validated_data['fcm_token'],
#                 'device_type': serializer.validated_data['device_type'],
#                 'is_active': True
#             }
#         )
        
#         return Response(UserDeviceSerializer(device).data)

# class UserListView(generics.ListAPIView):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer
#     permission_classes = [permissions.IsAuthenticated]
#     filterset_fields = ['role', 'is_active']
#     search_fields = ['email', 'first_name', 'last_name', 'phone_number']

# class UserActivityLogView(generics.ListAPIView):
#     serializer_class = UserActivityLogSerializer
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get_queryset(self):
#         if self.request.user.role == 'admin':
#             return UserActivityLog.objects.all()
#         return UserActivityLog.objects.filter(user=self.request.user)

# class CheckAuthView(APIView):
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get(self, request):
#         return Response({
#             'authenticated': True,
#             'user': UserSerializer(request.user).data
#         })



# apps/accounts/views.py
import logging
import uuid
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from rest_framework import status, permissions, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser  # <-- ADD THIS
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
from django.contrib.auth.password_validation import validate_password
from apps.accounts import serializers
from .email_helper import EmailHelper
from rest_framework.pagination import PageNumberPagination

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
        
        user.login_attempts = 0
        user.account_locked = False
        user.lock_expiry = None
        user.last_login = timezone.now()
        user.save()
        
        refresh = RefreshToken.for_user(user)
        
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
        
        if not user.check_password(serializer.validated_data['old_password']):
            raise serializers.ValidationError('Old password is incorrect')
        
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
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'message': 'If an account exists with this email, a password reset link has been sent.'
            })
        
        token = uuid.uuid4().hex[:32]
        token_hash = bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt())
        
        PasswordResetToken.objects.update_or_create(
            user=user,
            defaults={
                'token_hash': token_hash.decode('utf-8'),
                'expires_at': timezone.now() + timezone.timedelta(hours=1)
            }
        )
        
        try:
            self.send_reset_email(user, token)
            return Response({'message': 'Password reset link sent to your email'})
        except Exception as e:
            logger.error(f'Failed to send password reset email to {email}: {str(e)}')
            return Response(
                {
                    'error': 'Failed to send password reset email. Please try again later.',
                    'details': str(e) if settings.DEBUG else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def send_reset_email(self, user, token):
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        
        subject = 'Password Reset - ECORET'
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .button {{ 
                    display: inline-block; 
                    padding: 12px 24px; 
                    background: #4CAF50; 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .warning {{ color: #f44336; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ECORET Password Reset</h1>
                </div>
                <div class="content">
                    <h2>Hello {user.first_name or user.email},</h2>
                    <p>We received a request to reset your password for your ECORET account.</p>
                    <p>Click the button below to reset your password:</p>
                    <p style="text-align: center;">
                        <a href="{reset_link}" class="button">Reset Password</a>
                    </p>
                    <p>Or copy and paste this link in your browser:</p>
                    <p><a href="{reset_link}">{reset_link}</a></p>
                    <p class="warning">This link will expire in 1 hour.</p>
                    <p>If you didn't request a password reset, please ignore this email.</p>
                    <hr>
                    <p><strong>Security Tip:</strong> Never share your password with anyone.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2026 ECORET MicroCredite Agency. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        ECORET Password Reset
        
        Hello {user.first_name or user.email},
        
        We received a request to reset your password for your ECORET account.
        
        Click the link below to reset your password:
        {reset_link}
        
        This link will expire in 1 hour.
        
        If you didn't request a password reset, please ignore this email.
        
        Security Tip: Never share your password with anyone.
        
        © 2026 ECORET. All rights reserved.
        """
        
        EmailHelper.send_email(
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            recipient_email=user.email
        )

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
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
        
        user = valid_token.user
        user.set_password(new_password)
        user.save()
        
        valid_token.delete()
        
        UserActivityLog.objects.create(
            user=user,
            action='reset_password',
            details={'ip': request.META.get('REMOTE_ADDR')}
        )
        
        return Response({'message': 'Password reset successfully'})

# apps/accounts/views.py
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from PIL import Image
import io
import os

class UserProfileView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            file = request.FILES['profile_picture']
            
            # Validate image
            try:
                # Check if it's a valid image
                img = Image.open(file)
                img.verify()  # Verify image
                
                # Reset file pointer after verify
                file.seek(0)
                
                # Save the file
                request.user.profile_picture = file
                request.user.save()
                logger.info(f"✅ Profile picture updated for user {request.user.email}")
                
            except Exception as e:
                logger.error(f"❌ Invalid image uploaded: {str(e)}")
                return Response(
                    {'profile_picture': 'Invalid image file. Please upload a valid image (JPG, PNG, GIF).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Update other fields
        # Exclude profile_picture from data to avoid validation issues
        data = request.data.copy()
        data.pop('profile_picture', None)
        
        serializer = UserSerializer(request.user, data=data, partial=True)
        
        if not serializer.is_valid():
            logger.error(f"Profile update errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action='update_profile',
            details={
                'ip': request.META.get('REMOTE_ADDR'),
                'updated_fields': list(request.data.keys())
            }
        )
        
        return Response(serializer.data)
    
class UserDeviceRegisterView(APIView):
    def post(self, request):
        serializer = UserDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
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
    pagination_class = PageNumberPagination

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

# ==================== ADMIN USER MANAGEMENT VIEWS ====================

class AdminUserUpdateView(APIView):
    """
    Admin view to update user status (enable/disable)
    Only accessible to ECORET Admins
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, pk=None):
        # Check if user is admin
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET Admins can update user status'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            user = User.objects.get(id=pk)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Don't allow disabling yourself
        if user.id == request.user.id:
            return Response(
                {'error': 'You cannot disable your own account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response(
                {'error': 'is_active field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_active = is_active
        user.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action='admin_update_user_status',
            details={
                'target_user_id': str(user.id),
                'target_user_email': user.email,
                'is_active': is_active
            }
        )
        
        return Response({
            'message': f"User {'enabled' if is_active else 'disabled'} successfully",
            'user': UserSerializer(user).data
        })