# apps/accounts/views.py
import logging
import secrets
import uuid
import bcrypt
import smtplib
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from PIL import Image
import io
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from rest_framework import status, permissions, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import logout
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from apps.accounts import serializers
from .email_helper import EmailHelper
from rest_framework.pagination import PageNumberPagination

from .models import User, UserDevice, PasswordResetToken, UserActivityLog, AdminRequest
from .serializers import (
    UserSerializer, LoginSerializer, RegisterSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, UserDeviceSerializer, UserActivityLogSerializer,
    AdminRequestSerializer, AdminRequestCreateSerializer
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

# apps/accounts/views.py - Updated RegisterView

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        # Get the role from request data - default to 'member' if not provided
        role = request.data.get('role', 'member')
        print(f"📝 Registration with role: {role}")  # Debug log
        
        # Create serializer with the role included
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Save the user but don't commit yet so we can modify
        user = serializer.save()
        
        # Update the role if it was provided
        if role in ['admin', 'chairman', 'secretary', 'treasurer', 'member']:
            user.role = role
            user.save()
            print(f"✅ User role set to: {user.role}")  # Debug log
        
        # Handle admin role specifically
        if role == 'admin':
            # For admin role, set is_active to False until approved
            user.is_active = False
            user.save()
            
            # Create admin request automatically
            admin_request = AdminRequest.objects.create(
                user=user,
                full_name=user.get_full_name(),
                email=user.email,
                phone_number=user.phone_number,
                reason=request.data.get('reason', 'No reason provided'),
                status='pending'
            )
            
            UserActivityLog.objects.create(
                user=user,
                action='admin_registration_request',
                details={
                    'ip': request.META.get('REMOTE_ADDR'),
                    'request_id': str(admin_request.id)
                }
            )
            
            # Notify admins (optional)
            self.notify_admins(admin_request)
            
            return Response({
                'message': 'Admin request submitted successfully. Please wait for approval from existing ECORET Administrators.',
                'user': UserSerializer(user).data,
                'admin_request': AdminRequestSerializer(admin_request).data
            }, status=status.HTTP_201_CREATED)
        else:
            # For chairman/member, activate immediately
            user.is_active = True
            user.save()
            
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
    
    def notify_admins(self, admin_request):
        """Notify existing admins about new admin request"""
        try:
            admins = User.objects.filter(role='admin', is_active=True)
            if not admins:
                print("⚠️ No admins found to notify")
                return
            
            for admin in admins:
                print(f"📧 Notifying admin: {admin.email}")
                try:
                    send_mail(
                        subject=f'New Admin Request - {admin_request.user.email}',
                        message=f"""
                        A new admin request has been submitted.
                        
                        User: {admin_request.user.get_full_name()}
                        Email: {admin_request.user.email}
                        Phone: {admin_request.user.phone_number}
                        Reason: {admin_request.reason}
                        
                        Please review this request in the admin dashboard.
                        """,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[admin.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"❌ Failed to send email to {admin.email}: {str(e)}")
                    
        except Exception as e:
            print(f"❌ Failed to notify admins: {str(e)}")
            

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
        
        token = ''.join(secrets.choice('0123456789') for _ in range(6))
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
        subject = 'Password Reset - ECORET'

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #0B6B80; }}
                .code-box {{
                    background: #fff;
                    border: 2px dashed #4CAF50;
                    border-radius: 8px;
                    padding: 16px;
                    text-align: center;
                    font-size: 28px;
                    font-weight: bold;
                    letter-spacing: 2px;
                    color: #4CAF50;
                    margin: 20px 0;
                }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .warning {{ color: #0B6B80; font-weight: bold; }}
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
                    <p>Enter this code in the app to reset your password:</p>
                    <div class="code-box">{token}</div>
                    <p class="warning">This code will expire in 1 hour.</p>
                    <p>If you didn't request a password reset, please ignore this email.</p>
                    <hr>
                    <p><strong>Security Tip:</strong> Never share this code with anyone.</p>
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

        Enter this code in the app to reset your password:

        {token}

        This code will expire in 1 hour.

        If you didn't request a password reset, please ignore this email.

        Security Tip: Never share this code with anyone.

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


# ==================== ADMIN REQUEST VIEWS ====================

class AdminRequestView(APIView):
    """View to handle admin requests"""
    
    def post(self, request):
        """Submit an admin request"""
        # Check if user is already an admin
        if request.user.role == 'admin':
            return Response(
                {'error': 'You are already an administrator'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for existing pending request
        if AdminRequest.objects.filter(user=request.user, status='pending').exists():
            return Response(
                {'error': 'You already have a pending admin request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for existing approved request
        if AdminRequest.objects.filter(user=request.user, status='approved').exists():
            return Response(
                {'error': 'Your admin request has already been approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AdminRequestCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        admin_request = serializer.save()
        
        # Log the activity
        UserActivityLog.objects.create(
            user=request.user,
            action='admin_request_submitted',
            details={
                'ip': request.META.get('REMOTE_ADDR'),
                'request_id': str(admin_request.id)
            }
        )
        
        # Notify existing admins (optional)
        self.notify_admins(admin_request)
        
        return Response({
            'message': 'Admin request submitted successfully. Please wait for approval from existing ECORET Administrators.',
            'request': AdminRequestSerializer(admin_request).data
        }, status=status.HTTP_201_CREATED)
    
    def get(self, request):
        """Get user's admin requests"""
        if request.user.role == 'admin':
            # Admins can see all requests
            requests = AdminRequest.objects.all()
            serializer = AdminRequestSerializer(requests, many=True)
            return Response(serializer.data)
        else:
            # Regular users can only see their own requests
            requests = AdminRequest.objects.filter(user=request.user)
            serializer = AdminRequestSerializer(requests, many=True)
            return Response(serializer.data)
    
    def notify_admins(self, admin_request):
        """Notify existing admins about new request"""
        try:
            admins = User.objects.filter(role='admin', is_active=True)
            if not admins:
                return
            
            for admin in admins:
                logger.info(f"New admin request from {admin_request.user.email} - Notifying {admin.email}")
        except Exception as e:
            logger.error(f"Failed to notify admins: {str(e)}")


class AdminRequestDetailView(APIView):
    """View to handle individual admin request actions"""
    
    def get_object(self, pk):
        try:
            return AdminRequest.objects.get(id=pk)
        except AdminRequest.DoesNotExist:
            return None
    
    def post(self, request, pk):
        """Approve or reject an admin request"""
        admin_request = self.get_object(pk)
        
        if not admin_request:
            return Response(
                {'error': 'Admin request not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is admin
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET Administrators can approve or reject requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if request is still pending
        if admin_request.status != 'pending':
            return Response(
                {'error': f'This request has already been {admin_request.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action = request.data.get('action')
        if action not in ['approve', 'reject']:
            return Response(
                {'error': 'Action must be "approve" or "reject"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            if action == 'approve':
                admin_request.status = 'approved'
                admin_request.reviewed_by = request.user
                admin_request.reviewed_at = timezone.now()
                admin_request.save()
                
                # Update user role to admin
                user = admin_request.user
                user.role = 'admin'
                user.is_active = True
                user.save()
                
                message = f'Admin request for {user.email} has been approved.'
                
            else:  # reject
                admin_request.status = 'rejected'
                admin_request.reviewed_by = request.user
                admin_request.reviewed_at = timezone.now()
                admin_request.save()
                
                message = f'Admin request for {admin_request.user.email} has been rejected.'
        
        # Log the activity
        UserActivityLog.objects.create(
            user=request.user,
            action=f'admin_request_{action}ed',
            details={
                'ip': request.META.get('REMOTE_ADDR'),
                'target_user_id': str(admin_request.user.id),
                'target_user_email': admin_request.user.email,
                'request_id': str(admin_request.id)
            }
        )
        
        return Response({
            'message': message,
            'request': AdminRequestSerializer(admin_request).data
        })


class PendingAdminRequestsView(APIView):
    """View to get all pending admin requests"""
    
    def get(self, request):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET Administrators can view pending requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        pending_requests = AdminRequest.objects.filter(status='pending').order_by('-created_at')
        serializer = AdminRequestSerializer(pending_requests, many=True)
        return Response(serializer.data)