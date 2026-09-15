# apps/accounts/tests/test_integration.py
import json
import uuid
from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core import mail
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from apps.accounts.models import UserDevice, PasswordResetToken, UserActivityLog

User = get_user_model()

class AuthIntegrationTests(TestCase):
    """Integration tests for authentication views"""
    
    def setUp(self):
        """Set up test data and client"""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            role='user',
            is_active=True
        )
        
        # Create admin user
        self.admin = User.objects.create_user(
            email='admin@ecoret.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_active=True
        )
        
        # URLs
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.change_password_url = reverse('change_password')
        self.forgot_password_url = reverse('forgot_password')
        self.reset_password_url = reverse('reset_password')
        self.profile_url = reverse('user_profile')
        self.check_auth_url = reverse('check_auth')
        
    def test_user_registration_success(self):
        """Test successful user registration"""
        data = {
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'User',
            'phone_number': '+1234567890'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'User registered successfully')
        self.assertEqual(response.data['user']['email'], 'newuser@example.com')
        self.assertEqual(response.data['user']['first_name'], 'New')
        
        # Check user was created in database
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
        
        # Check activity log was created
        user = User.objects.get(email='newuser@example.com')
        self.assertTrue(UserActivityLog.objects.filter(
            user=user,
            action='register'
        ).exists())

    def test_user_registration_duplicate_email(self):
        """Test registration with existing email"""
        data = {
            'email': 'test@example.com',  # Already exists
            'password': 'StrongPass123!',
            'first_name': 'Duplicate',
            'last_name': 'User'
        }
        
        response = self.client.post(self.register_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_user_login_success(self):
        """Test successful login"""
        data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        
        # Check activity log was created
        user = User.objects.get(email='test@example.com')
        self.assertTrue(UserActivityLog.objects.filter(
            user=user,
            action='login'
        ).exists())

    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        data = {
            'email': 'test@example.com',
            'password': 'WrongPassword123!'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('access', response.data)

    def test_user_login_inactive_user(self):
        """Test login with inactive user"""
        self.user.is_active = False
        self.user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('access', response.data)

    def test_user_logout_success(self):
        """Test successful logout"""
        # First login to get tokens
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Set auth header for logout
        access_token = login_response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Logout
        logout_data = {'refresh': refresh_token}
        response = self.client.post(self.logout_url, logout_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Logged out successfully')
        
        # Check activity log was created
        user = User.objects.get(email='test@example.com')
        self.assertTrue(UserActivityLog.objects.filter(
            user=user,
            action='logout'
        ).exists())

    def test_change_password_success(self):
        """Test changing password successfully"""
        # Login first
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Change password
        data = {
            'old_password': 'TestPassword123!',
            'new_password': 'NewPassword456!'
        }
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Password changed successfully')
        
        # Check activity log was created
        user = User.objects.get(email='test@example.com')
        self.assertTrue(UserActivityLog.objects.filter(
            user=user,
            action='change_password'
        ).exists())
        
        # Verify new password works
        self.client.credentials()  # Clear credentials
        login_data = {
            'email': 'test@example.com',
            'password': 'NewPassword456!'
        }
        new_login_response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(new_login_response.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old_password(self):
        """Test changing password with wrong old password"""
        # Login
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Try to change with wrong old password
        data = {
            'old_password': 'WrongPassword123!',
            'new_password': 'NewPassword456!'
        }
        response = self.client.post(self.change_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.accounts.views.EmailHelper.send_email')
    def test_forgot_password_success(self, mock_send_email):
        """Test successful password reset request"""
        mock_send_email.return_value = True
        
        data = {'email': 'test@example.com'}
        response = self.client.post(self.forgot_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['message'], 
            'If an account exists with this email, a password reset link has been sent.'
        )
        
        # Check reset token was created
        user = User.objects.get(email='test@example.com')
        self.assertTrue(PasswordResetToken.objects.filter(user=user).exists())
        
        # Check email was sent
        mock_send_email.assert_called_once()
        
        # Get the token from the database to verify
        reset_token = PasswordResetToken.objects.get(user=user)
        self.assertIsNotNone(reset_token.token_hash)
        self.assertGreater(reset_token.expires_at, timezone.now())

    def test_forgot_password_nonexistent_email(self):
        """Test password reset for nonexistent email - should still return success"""
        data = {'email': 'nonexistent@example.com'}
        response = self.client.post(self.forgot_password_url, data, format='json')
        
        # Should return same message for security
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['message'], 
            'If an account exists with this email, a password reset link has been sent.'
        )
        
        # No reset token should be created
        self.assertEqual(PasswordResetToken.objects.count(), 0)

    def test_reset_password_success(self):
        """Test successful password reset"""
        # First, create a reset token
        token = uuid.uuid4().hex[:32]
        user = User.objects.get(email='test@example.com')
        
        PasswordResetToken.objects.create(
            user=user,
            token_hash=token,  # In real code this would be hashed
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        data = {
            'token': token,
            'new_password': 'ResetPassword123!'
        }
        response = self.client.post(self.reset_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Password reset successfully')
        
        # Check activity log was created
        self.assertTrue(UserActivityLog.objects.filter(
            user=user,
            action='reset_password'
        ).exists())
        
        # Verify new password works
        login_data = {
            'email': 'test@example.com',
            'password': 'ResetPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_reset_password_expired_token(self):
        """Test password reset with expired token"""
        token = uuid.uuid4().hex[:32]
        user = User.objects.get(email='test@example.com')
        
        PasswordResetToken.objects.create(
            user=user,
            token_hash=token,
            expires_at=timezone.now() - timedelta(hours=1)  # Expired
        )
        
        data = {
            'token': token,
            'new_password': 'ResetPassword123!'
        }
        response = self.client.post(self.reset_password_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_view_success(self):
        """Test getting user profile"""
        # Login
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(self.profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['first_name'], 'Test')
        self.assertEqual(response.data['last_name'], 'User')

    def test_profile_update_success(self):
        """Test updating user profile"""
        # Login
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone_number': '+9876543210'
        }
        response = self.client.put(self.profile_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['first_name'], 'Updated')
        self.assertEqual(response.data['last_name'], 'Name')
        self.assertEqual(response.data['phone_number'], '+9876543210')
        
        # Check activity log was created
        user = User.objects.get(email='test@example.com')
        self.assertTrue(UserActivityLog.objects.filter(
            user=user,
            action='update_profile'
        ).exists())

    def test_check_auth_authenticated(self):
        """Test authentication check endpoint for authenticated user"""
        # Login
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(self.login_url, login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(self.check_auth_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['authenticated'])
        self.assertEqual(response.data['user']['email'], 'test@example.com')

    def test_check_auth_unauthenticated(self):
        """Test authentication check endpoint for unauthenticated user"""
        response = self.client.get(self.check_auth_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminUserManagementTests(TestCase):
    """Integration tests for admin user management views"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create regular user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            role='user',
            is_active=True
        )
        
        # Create admin user
        self.admin = User.objects.create_user(
            email='admin@ecoret.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_active=True
        )
        
        self.admin_update_url = lambda pk: reverse('admin_user_update', kwargs={'pk': pk})
        
    def test_admin_can_disable_user(self):
        """Test admin can disable a user"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Disable user
        data = {'is_active': False}
        response = self.client.patch(self.admin_update_url(self.user.id), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['message'], 
            'User disabled successfully'
        )
        
        # Verify user is disabled
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_admin_can_enable_user(self):
        """Test admin can enable a user"""
        # First disable user
        self.user.is_active = False
        self.user.save()
        
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Enable user
        data = {'is_active': True}
        response = self.client.patch(self.admin_update_url(self.user.id), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['message'], 
            'User enabled successfully'
        )
        
        # Verify user is enabled
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_regular_user_cannot_disable_users(self):
        """Test regular user cannot disable other users"""
        # Login as regular user
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Try to disable another user
        other_user = User.objects.create_user(
            email='other@example.com',
            password='Test123!',
            role='user'
        )
        
        data = {'is_active': False}
        response = self.client.patch(self.admin_update_url(other_user.id), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.data)

    def test_admin_cannot_disable_self(self):
        """Test admin cannot disable their own account"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Try to disable self
        data = {'is_active': False}
        response = self.client.patch(self.admin_update_url(self.admin.id), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error'], 
            'You cannot disable your own account'
        )

    def test_admin_update_nonexistent_user(self):
        """Test admin updating nonexistent user"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Try to update nonexistent user
        data = {'is_active': False}
        response = self.client.patch(
            reverse('admin_user_update', kwargs={'pk': 99999}), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserDeviceTests(TestCase):
    """Integration tests for user device management"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            role='user',
            is_active=True
        )
        
        self.device_url = reverse('device_register')
        
    def test_register_device_success(self):
        """Test registering a new device"""
        # Login
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        data = {
            'device_id': 'test-device-123',
            'fcm_token': 'fcm-token-123',
            'device_type': 'android'
        }
        response = self.client.post(self.device_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['device_id'], 'test-device-123')
        self.assertEqual(response.data['device_type'], 'android')
        self.assertTrue(response.data['is_active'])
        
        # Check device was created in database
        self.assertTrue(UserDevice.objects.filter(
            user=self.user,
            device_id='test-device-123'
        ).exists())

    def test_register_device_update_existing(self):
        """Test updating an existing device"""
        # First create a device
        device = UserDevice.objects.create(
            user=self.user,
            device_id='test-device-123',
            fcm_token='old-token',
            device_type='ios',
            is_active=True
        )
        
        # Login
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Update device
        data = {
            'device_id': 'test-device-123',
            'fcm_token': 'new-token',
            'device_type': 'android'
        }
        response = self.client.post(self.device_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify device was updated
        device.refresh_from_db()
        self.assertEqual(device.fcm_token, 'new-token')
        self.assertEqual(device.device_type, 'android')
        self.assertTrue(device.is_active)


class UserListViewTests(TestCase):
    """Integration tests for user list view"""
    
    def setUp(self):
        self.client = APIClient()
        
        # Create multiple users
        self.users = []
        for i in range(5):
            user = User.objects.create_user(
                email=f'user{i}@example.com',
                password=f'Pass{i}123!',
                first_name=f'User{i}',
                last_name=f'Last{i}',
                role='user',
                is_active=True
            )
            self.users.append(user)
        
        self.admin = User.objects.create_user(
            email='admin@ecoret.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_active=True
        )
        
        self.user_list_url = reverse('user_list')
        
    def test_admin_can_list_users(self):
        """Test admin can list all users"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(self.user_list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, dict)  # Paginated response
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 5)  # At least 5 users

    def test_user_can_list_other_users(self):
        """Test regular user can list other users"""
        # Login as regular user
        login_data = {
            'email': 'user0@example.com',
            'password': 'Pass0!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(self.user_list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_user_list_search(self):
        """Test user list search functionality"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Search by email
        response = self.client.get(f"{self.user_list_url}?search=user1@example.com")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], 'user1@example.com')

    def test_user_list_pagination(self):
        """Test user list pagination"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        # Get first page with small page size
        response = self.client.get(f"{self.user_list_url}?page=1&page_size=2")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertLessEqual(len(response.data['results']), 2)


class UserActivityLogTests(TestCase):
    """Integration tests for user activity log"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            role='user',
            is_active=True
        )
        
        self.admin = User.objects.create_user(
            email='admin@ecoret.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_active=True
        )
        
        # Create some activity logs
        for i in range(3):
            UserActivityLog.objects.create(
                user=self.user,
                action='login',
                details={'ip': '127.0.0.1'},
                ip_address='127.0.0.1',
                user_agent='test-agent'
            )
        
        self.activity_log_url = reverse('activity_log')
        
    def test_user_can_view_own_activity(self):
        """Test regular user can view their own activity logs"""
        # Login as regular user
        login_data = {
            'email': 'test@example.com',
            'password': 'TestPassword123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(self.activity_log_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)  # Should see their logs
        for log in response.data['results']:
            self.assertEqual(log['user'], self.user.id)

    def test_admin_can_view_all_activity(self):
        """Test admin can view all activity logs"""
        # Login as admin
        login_data = {
            'email': 'admin@ecoret.com',
            'password': 'AdminPass123!'
        }
        login_response = self.client.post(reverse('login'), login_data, format='json')
        access_token = login_response.data['access']
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        response = self.client.get(self.activity_log_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin should see all logs including their own and the user's
        self.assertGreaterEqual(len(response.data['results']), 3)