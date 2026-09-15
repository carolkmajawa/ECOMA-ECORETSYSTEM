# apps/ussd/tests.py - COMPLETE WORKING VERSION
import json
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from apps.groups.models import Group, GroupMember
from apps.accounts.models import User
from apps.savings.models import Saving
from apps.loans.models import Loan, LoanSettings
from apps.attendance.models import AttendanceCase

User = get_user_model()

class USSDBaseTest(TestCase):
    """Base test class for USSD tests"""
    
    def setUp(self):
        self.client = APIClient()
        self.session_id = 'session123'
        self.group_code = '123456'
        
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
        
        # Create test user
        self.test_user = User.objects.create_user(
            email='test@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            phone_number='+265888888888',
            role='member',
            is_active=True
        )
        
        # Create group with numeric code
        self.group = Group.objects.create(
            group_name='Test Savings Group',
            group_code=self.group_code,
            chairman=self.chairman,
            is_active=True
        )
        
        # Create group member (chairman as member)
        self.chairman_member = GroupMember.objects.create(
            group=self.group,
            user=self.chairman,
            full_name='John Chairman',
            phone_number='+2222222222',
            national_id='0987654321',
            is_active=True
        )
        
        # Create test user as group member
        self.group_member = GroupMember.objects.create(
            group=self.group,
            user=self.test_user,
            full_name='Test User',
            phone_number='+265888888888',
            national_id='1234567890',
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
        
        # Create an attendance case
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
        
        # USSD URL
        self.ussd_url = reverse('ussd-handler')
    
    def _make_ussd_request(self, text, phone='+265888888888'):
        """Helper to make a USSD request"""
        data = {
            'sessionId': self.session_id,
            'serviceCode': '*384#',
            'phoneNumber': phone,
            'text': text
        }
        return self.client.post(self.ussd_url, data)
    
    def _login_to_ussd(self, phone='+265888888888'):
        """Helper to simulate USSD login with language and group code"""
        self._make_ussd_request('', phone)
        self._make_ussd_request('1', phone)
        response = self._make_ussd_request(f'1*{self.group_code}', phone)
        return response


class USSDLanguageTests(USSDBaseTest):
    """Tests for USSD language selection"""
    
    def test_welcome_language_selection(self):
        """Test language selection screen"""
        response = self._make_ussd_request('')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('1. English', content)
        self.assertIn('2. Chichewa', content)
    
    def test_select_english_language(self):
        """Test selecting English language"""
        self._make_ussd_request('')
        response = self._make_ussd_request('1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Group Code', content)
    
    def test_select_chichewa_language(self):
        """Test selecting Chichewa language"""
        self._make_ussd_request('')
        response = self._make_ussd_request('2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.decode())


class USSDGroupCodeTests(USSDBaseTest):
    """Tests for USSD group code entry"""
    
    def test_valid_group_code(self):
        """Test entering a valid group code"""
        self._make_ussd_request('')
        self._make_ussd_request('1')
        response = self._make_ussd_request(f'1*{self.group_code}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Welcome', content)
        self.assertIn('Take a Loan', content)
    
    def test_invalid_group_code(self):
        """Test entering an invalid group code"""
        self._make_ussd_request('')
        self._make_ussd_request('1')
        response = self._make_ussd_request('1*999999')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Invalid group code', content)
    
    def test_unregistered_user(self):
        """Test user not registered in group"""
        self._make_ussd_request('')
        self._make_ussd_request('1')
        response = self._make_ussd_request(f'1*{self.group_code}', phone='+265111111111')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('not registered', content.lower())


class USSDMainMenuTests(USSDBaseTest):
    """Tests for USSD main menu"""
    
    def test_main_menu_options(self):
        """Test main menu displays correctly"""
        response = self._login_to_ussd()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Welcome Test User', content)
        self.assertIn('Take a Loan', content)
        self.assertIn('Deposit', content)
        self.assertIn('Check Balance', content)
        self.assertIn('My Info', content)
        self.assertIn('View Case Penalties', content)
    
    def test_take_loan_option(self):
        """Test selecting Take Loan option"""
        self._login_to_ussd()
        response = self._make_ussd_request(f'1*{self.group_code}*1')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Take a Loan', content)
        self.assertIn('Group Loan', content)
        self.assertIn('ECORET Loan', content)
    
    def test_deposit_option(self):
        """Test selecting Deposit option"""
        self._login_to_ussd()
        response = self._make_ussd_request(f'1*{self.group_code}*2')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Deposit Options', content)
        self.assertIn('Repay Loan', content)
        self.assertIn('Pay for Savings', content)


class USSDLoanTests(USSDBaseTest):
    """Tests for USSD loan functionality"""
    
    def test_group_loan_amount_prompt(self):
        """Test group loan amount prompt"""
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*1')
        response = self._make_ussd_request(f'1*{self.group_code}*1*1')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Enter loan amount in MK', content)
        self.assertIn('Minimum amount is MK1,000', content)
        self.assertIn('Maximum amount is MK500,000', content)
    
    @patch('apps.ussd.services.loans.issue_loan_otp')
    def test_loan_amount_entered(self, mock_issue_otp):
        """Test entering a valid loan amount"""
        mock_issue_otp.return_value = ('123456', 'corr-123')
        
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*1')
        self._make_ussd_request(f'1*{self.group_code}*1*1')
        response = self._make_ussd_request(f'1*{self.group_code}*1*1*50000')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Loan Summary', content)
        self.assertIn('Enter OTP', content)
    
    def test_loan_amount_below_minimum(self):
        """Test entering loan amount below minimum"""
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*1')
        self._make_ussd_request(f'1*{self.group_code}*1*1')
        response = self._make_ussd_request(f'1*{self.group_code}*1*1*500')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Invalid amount', content)


class USSDDepositTests(USSDBaseTest):
    """Tests for USSD deposit functionality"""
    
    def test_repayment_amount_prompt(self):
        """Test repayment amount prompt shows loan balance"""
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*2')
        response = self._make_ussd_request(f'1*{self.group_code}*2*1')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('MK55,000', content)
        self.assertIn('repayment amount', content.lower())
    
    @patch('apps.ussd.services.payments.payment_service.start_stk_push')
    def test_repayment_starts_payment(self, mock_payment):
        """Test repayment starts mobile money payment"""
        mock_payment.return_value = {
            'reference': 'ref-123',
            'payload': {'test': 'data'}
        }
        
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*2')
        self._make_ussd_request(f'1*{self.group_code}*2*1')
        response = self._make_ussd_request(f'1*{self.group_code}*2*1*5000')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('payment request has been sent', content.lower())
        self.assertIn('1. Confirm payment', content)
        mock_payment.assert_called_once()


class USSDCaseTests(USSDBaseTest):
    """Tests for USSD case penalty viewing"""
    
    def test_view_cases(self):
        """Test viewing case penalties"""
        self._login_to_ussd()
        response = self._make_ussd_request(f'1*{self.group_code}*5')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Case', content)
        self.assertIn('Penalties', content)


class USSDInfoTests(USSDBaseTest):
    """Tests for USSD member info"""
    
    def test_my_info(self):
        """Test viewing member info"""
        self._login_to_ussd()
        response = self._make_ussd_request(f'1*{self.group_code}*4')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Name', content)
        self.assertIn('Test User', content)


class USSDShortcutsTests(USSDBaseTest):
    """Tests for USSD shortcuts"""
    
    def test_00_goes_to_main_menu(self):
        """Test '00' goes to main menu from any screen"""
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*1')
        self._make_ussd_request(f'1*{self.group_code}*1*1')
        response = self._make_ussd_request(f'1*{self.group_code}*1*1*00')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Welcome Test User', content)
        self.assertIn('Take a Loan', content)
    
    def test_0_goes_back(self):
        """Test '0' goes back one step"""
        self._login_to_ussd()
        self._make_ussd_request(f'1*{self.group_code}*1')
        self._make_ussd_request(f'1*{self.group_code}*1*1')
        response = self._make_ussd_request(f'1*{self.group_code}*1*1*0')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('Take a Loan', content)