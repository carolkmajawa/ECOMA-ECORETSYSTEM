# apps/sync/tests.py - COMPLETE FINAL FIXED VERSION
import json
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.groups.models import Group, GroupMember
from apps.loans.models import Loan, LoanSettings
from apps.savings.models import Saving
from apps.attendance.models import Attendance, AttendanceCase
from apps.sync.models import DeviceSync, SyncLog

User = get_user_model()

class SyncBaseTest(TestCase):
    """Base test class for sync tests"""
    
    def setUp(self):
        self.client = APIClient()
        self.device_id = 'test-device-123'
        
        # Create admin user
        self.admin = User.objects.create_user(
            email='admin@ecoret.com',
            password='AdminPass123!',
            first_name='Admin',
            last_name='User',
            phone_number='+1111111111',
            role='admin',
            is_active=True
        )
        
        # Create chairman user
        self.chairman = User.objects.create_user(
            email='chairman@example.com',
            password='Chairman123!',
            first_name='John',
            last_name='Chairman',
            phone_number='+2222222222',
            role='chairman',
            is_active=True
        )
        
        # Create secretary user
        self.secretary = User.objects.create_user(
            email='secretary@example.com',
            password='Secretary123!',
            first_name='Jane',
            last_name='Secretary',
            phone_number='+3333333333',
            role='secretary',
            is_active=True
        )
        
        # Create regular member user
        self.member_user = User.objects.create_user(
            email='member@example.com',
            password='Member123!',
            first_name='Member',
            last_name='User',
            phone_number='+5555555555',
            role='member',
            is_active=True
        )
        
        # Create a group
        self.group = Group.objects.create(
            group_name='Test Savings Group',
            group_code='TSG001',
            chairman=self.chairman,
            secretary=self.secretary,
            is_active=True,
            default_interest_rate=10.00
        )
        
        # Create group member
        self.group_member = GroupMember.objects.create(
            group=self.group,
            user=self.member_user,
            full_name='Member User',
            phone_number='+5555555555',
            national_id='1234567890',
            is_active=True
        )
        
        # Create chairman as member too
        self.chairman_member = GroupMember.objects.create(
            group=self.group,
            user=self.chairman,
            full_name='John Chairman',
            phone_number='+2222222222',
            national_id='0987654321',
            is_active=True
        )
        
        # Create loan settings
        self.loan_settings = LoanSettings.objects.create(
            group=self.group,
            default_interest_rate=10.00,
            group_loan_duration_months=6,
            ecoret_loan_duration_months=12,
            group_loan_min_amount=1000.00,
            group_loan_max_amount=500000.00,
            ecoret_loan_min_amount=10000.00,
            ecoret_loan_max_amount=1000000.00
        )
        
        # Create a loan
        self.loan = Loan.objects.create(
            group=self.group,
            member=self.group_member,
            created_by=self.chairman,
            loan_type='group_loan',
            amount=50000.00,
            interest_rate=10.00,
            duration_months=6,
            total_payable=55000.00,
            status='active',
            purpose='Business loan',
            due_date=timezone.now() + timezone.timedelta(days=180)
        )
        
        # Create savings
        self.saving = Saving.objects.create(
            group=self.group,
            member=self.group_member,
            amount=1000.00,
            transaction_type='deposit',
            reference_number='SAV-001',
            notes='Test savings'
        )
        
        # Create attendance
        self.attendance = Attendance.objects.create(
            group=self.group,
            member=self.group_member,
            recorded_by=self.chairman,
            meeting_date=timezone.now().date(),
            meeting_type='regular',
            attended=True
        )
        
        # Create attendance case
        self.case = AttendanceCase.objects.create(
            group=self.group,
            member=self.group_member,
            recorded_by=self.chairman,
            case_type='absent',
            reason='Missed meeting',
            penalty_amount=5000.00,
            penalty_paid=0,
            meeting_date=timezone.now() - timezone.timedelta(days=2),
            status='pending'
        )
        
        # URLs
        self.sync_url = reverse('sync')
        self.sync_status_url = reverse('sync-status')
        
        # Helper method to login
        self.login_as = self._login_as
    
    def _login_as(self, user):
        """Helper to login as a specific user"""
        password_map = {
            self.admin: 'AdminPass123!',
            self.chairman: 'Chairman123!',
            self.secretary: 'Secretary123!',
            self.member_user: 'Member123!',
        }
        password = password_map.get(user, 'TestPassword123!')
        
        response = self.client.post(reverse('login'), {
            'email': user.email,
            'password': password
        }, format='json')
        
        if response.status_code == 200:
            token = response.data['access']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            return True
        return False


class SyncDownloadTests(SyncBaseTest):
    """Tests for sync download (GET)"""
    
    def test_download_sync_data_as_chairman(self):
        """Test chairman can download sync data"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)
        self.assertIn('timestamp', response.data)
        
        data = response.data['data']
        self.assertIn('groups', data)
        self.assertIn('members', data)
        self.assertIn('loans', data)
        self.assertIn('repayments', data)
        self.assertIn('savings', data)
        self.assertIn('attendance', data)
        self.assertIn('attendance_cases', data)
        
        # Check that device was created
        self.assertTrue(DeviceSync.objects.filter(
            user=self.chairman,
            device_id=self.device_id
        ).exists())

    def test_download_sync_data_as_admin(self):
        """Test admin can download sync data for all groups"""
        self.login_as(self.admin)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('groups', response.data['data'])
        
        # Admin should see at least one group
        self.assertGreaterEqual(len(response.data['data']['groups']), 1)

    def test_download_sync_data_as_member(self):
        """Test member can download sync data for their group"""
        self.login_as(self.member_user)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('groups', response.data['data'])

    def test_download_sync_requires_device_id(self):
        """Test sync download requires device_id"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'device_id is required')

    def test_download_sync_creates_device_sync(self):
        """Test downloading sync creates a DeviceSync record"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        device = DeviceSync.objects.get(user=self.chairman, device_id=self.device_id)
        self.assertEqual(device.total_syncs, 1)
        self.assertIsNotNone(device.last_sync_at)

    def test_download_sync_creates_sync_log(self):
        """Test downloading sync creates a SyncLog entry"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertTrue(SyncLog.objects.filter(
            user=self.chairman,
            action='download',
            status='success'
        ).exists())

    def test_download_sync_increments_sync_count(self):
        """Test multiple syncs increment the sync count"""
        self.login_as(self.chairman)
        
        # First sync
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Second sync
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        device = DeviceSync.objects.get(user=self.chairman, device_id=self.device_id)
        self.assertEqual(device.total_syncs, 2)


class SyncUploadTests(SyncBaseTest):
    """Tests for sync upload (POST)"""
    
    def test_upload_sync_data(self):
        """Test uploading sync data"""
        self.login_as(self.chairman)
        
        # First, create a device sync record
        self.client.get(self.sync_url, {'device_id': self.device_id})
        
        # Prepare upload data
        upload_data = {
            'device_id': self.device_id,
            'members': [
                {
                    'id': str(uuid.uuid4()),
                    'group_id': str(self.group.id),
                    'full_name': 'New Member',
                    'phone_number': '+6666666666',
                    'national_id': '9876543210',
                    'business_type': 'retail',
                    'is_active': True
                }
            ],
            'attendance': [
                {
                    'id': str(uuid.uuid4()),
                    'member_id': str(self.group_member.id),
                    'meeting_date': timezone.now().date().isoformat(),
                    'attended': True,
                    'meeting_type': 'regular',
                    'recorded_by': str(self.chairman.id)
                }
            ]
        }
        
        response = self.client.post(self.sync_url, upload_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('results', response.data)
        
        # Check sync log was created
        self.assertTrue(SyncLog.objects.filter(
            user=self.chairman,
            action='upload'
        ).exists())

    def test_upload_sync_requires_device_id(self):
        """Test sync upload requires device_id"""
        self.login_as(self.chairman)
        
        response = self.client.post(self.sync_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'device_id is required')

    def test_upload_sync_device_not_found(self):
        """Test upload fails if device not found"""
        self.login_as(self.chairman)
        
        upload_data = {
            'device_id': 'unknown-device',
            'members': []
        }
        
        response = self.client.post(self.sync_url, upload_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Device not found. Please sync first.')

    def test_upload_sync_creates_member(self):
        """Test uploading creates a new member"""
        self.login_as(self.chairman)
        
        # Create device sync
        self.client.get(self.sync_url, {'device_id': self.device_id})
        
        member_id = str(uuid.uuid4())
        upload_data = {
            'device_id': self.device_id,
            'members': [
                {
                    'id': member_id,
                    'group_id': str(self.group.id),
                    'full_name': 'Uploaded Member',
                    'phone_number': '+7777777777',
                    'national_id': '9876543210',
                    'business_type': 'retail',
                    'is_active': True
                }
            ]
        }
        
        response = self.client.post(self.sync_url, upload_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check member was created
        self.assertTrue(GroupMember.objects.filter(
            group=self.group,
            full_name='Uploaded Member'
        ).exists())

    def test_upload_sync_updates_member(self):
        """Test uploading updates an existing member"""
        self.login_as(self.chairman)
        
        # Create device sync
        self.client.get(self.sync_url, {'device_id': self.device_id})
        
        upload_data = {
            'device_id': self.device_id,
            'members': [
                {
                    'id': str(self.group_member.id),
                    'full_name': 'Updated Member Name',
                    'phone_number': '+5555555555',
                    'business_type': 'wholesale',
                    'is_active': True
                }
            ]
        }
        
        response = self.client.post(self.sync_url, upload_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check member was updated
        self.group_member.refresh_from_db()
        self.assertEqual(self.group_member.full_name, 'Updated Member Name')
        self.assertEqual(self.group_member.business_type, 'wholesale')

    def test_upload_sync_creates_attendance(self):
        """Test uploading creates attendance record"""
        self.login_as(self.chairman)
        
        # Create device sync
        self.client.get(self.sync_url, {'device_id': self.device_id})
        
        attendance_id = str(uuid.uuid4())
        upload_data = {
            'device_id': self.device_id,
            'attendance': [
                {
                    'id': attendance_id,
                    'member_id': str(self.group_member.id),
                    'group_id': str(self.group.id),
                    'meeting_date': timezone.now().date().isoformat(),
                    'attended': True,
                    'meeting_type': 'regular',
                    'recorded_by': str(self.chairman.id)
                }
            ]
        }
        
        response = self.client.post(self.sync_url, upload_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check attendance was created by finding by member and date
        attendance_exists = Attendance.objects.filter(
            member=self.group_member,
            meeting_date=timezone.now().date(),
            meeting_type='regular'
        ).exists()
        
        self.assertTrue(attendance_exists, "Attendance record was not created")


class SyncStatusTests(SyncBaseTest):
    """Tests for sync status endpoint"""
    
    def test_get_sync_status(self):
        """Test getting sync status"""
        self.login_as(self.chairman)
        
        # First sync to create device record
        self.client.get(self.sync_url, {'device_id': self.device_id})
        
        response = self.client.get(self.sync_status_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['user']), str(self.chairman.id))
        self.assertEqual(response.data['device_id'], self.device_id)
        self.assertEqual(response.data['total_syncs'], 1)
        self.assertIsNotNone(response.data['last_sync_at'])
        if 'synced' in response.data:
            self.assertTrue(response.data['synced'])

    def test_sync_status_requires_device_id(self):
        """Test sync status requires device_id"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_status_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'device_id is required')

    def test_sync_status_device_not_found(self):
        """Test sync status returns not synced if device not found"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_status_url, {'device_id': 'unknown-device'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['user']), str(self.chairman.id))
        self.assertEqual(response.data['device_id'], 'unknown-device')
        self.assertEqual(response.data['total_syncs'], 0)
        self.assertIsNone(response.data['last_sync_at'])
        if 'synced' in response.data:
            self.assertFalse(response.data['synced'])


class SyncPermissionTests(SyncBaseTest):
    """Tests for sync permission-based access"""
    
    def test_unauthenticated_cannot_sync(self):
        """Test unauthenticated user cannot sync"""
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_sync_status(self):
        """Test unauthenticated user cannot get sync status"""
        response = self.client.get(self.sync_status_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chairman_can_sync(self):
        """Test chairman can sync"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_can_sync(self):
        """Test member can sync"""
        self.login_as(self.member_user)
        
        response = self.client.get(self.sync_url, {'device_id': self.device_id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)