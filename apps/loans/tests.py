# apps/loans/tests.py
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.groups.models import Group, GroupMember
from apps.loans.models import (
    Loan, LoanRepayment, LoanRequest, LoanSettings,
    ECORETSettings, ECORETBankAccount
)
from apps.accounts.models import UserActivityLog

User = get_user_model()

class LoansBaseTest(TestCase):
    """Base test class with common setup for loans tests"""
    
    def setUp(self):
        self.client = APIClient()
        
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
        
        # Also add chairman as member
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
            ecoret_loan_max_amount=1000000.00,
            requires_guarantor=True,
            min_guarantors=2,
            grace_period_days=7,
            late_fee_percentage=0.00
        )
        
        # Create ECORET settings - REMOVE ecoret_service_fee if it doesn't exist
        self.ecoret_settings = ECORETSettings.objects.create(
            ecoret_loan_interest_rate=12.00,
            ecoret_loan_duration_months=12,
            ecoret_loan_min_amount=10000.00,
            ecoret_loan_max_amount=1000000.00
            # ecoret_service_fee removed - not a valid field
        )
        
        # Create ECORET bank account
        self.ecoret_account = ECORETBankAccount.objects.create(
            name='Main ECORET Account',
            account_number='1234567890',
            bank_name='National Bank',
            branch='Main Branch',
            balance=1000000.00,
            status='active',
            is_default=True
        )
        
        # URLs
        self.loans_list_url = reverse('loan-list')
        self.loan_requests_list_url = reverse('loan-request-list')
        self.loan_settings_list_url = reverse('loan-settings-list')
        self.ecoret_settings_list_url = reverse('ecoret-settings-list')
        self.ecoret_accounts_list_url = reverse('ecoret-account-list')
        
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
    
    def _create_loan(self, **kwargs):
        """Helper to create a test loan"""
        defaults = {
            'group': self.group,
            'member': self.group_member,
            'created_by': self.chairman,
            'loan_type': 'group_loan',
            'amount': 50000.00,
            'interest_rate': 10.00,
            'duration_months': 6,
            'total_payable': 55000.00,
            'status': 'pending',
            'purpose': 'Business expansion',
            'due_date': timezone.now() + timedelta(days=180)
        }
        defaults.update(kwargs)
        return Loan.objects.create(**defaults)


class LoanCreationTests(LoansBaseTest):
    """Tests for loan creation"""
    
    def test_chairman_can_create_loan(self):
        """Test chairman can create a loan for a member"""
        self.login_as(self.chairman)
        
        data = {
            'member': str(self.group_member.id),
            'amount': 50000.00,
            'purpose': 'Business expansion',
            'loan_type': 'group_loan'
        }
        
        response = self.client.post(self.loans_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount'], '50000.00')
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['loan_type'], 'group_loan')
        
        # Check activity log
        self.assertTrue(UserActivityLog.objects.filter(
            user=self.chairman,
            action='create_loan'
        ).exists())

    def test_loan_amount_validation_minimum(self):
        """Test loan amount is below minimum"""
        self.login_as(self.chairman)
        
        data = {
            'member': str(self.group_member.id),
            'amount': 500.00,  # Below minimum (1000)
            'purpose': 'Small loan',
            'loan_type': 'group_loan'
        }
        
        response = self.client.post(self.loans_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Minimum loan amount', str(response.data))

    def test_loan_amount_validation_maximum(self):
        """Test loan amount exceeds maximum"""
        self.login_as(self.chairman)
        
        data = {
            'member': str(self.group_member.id),
            'amount': 600000.00,  # Above maximum (500000)
            'purpose': 'Large loan',
            'loan_type': 'group_loan'
        }
        
        response = self.client.post(self.loans_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Maximum loan amount', str(response.data))

    def test_cannot_create_loan_for_inactive_member(self):
        """Test cannot create loan for inactive member"""
        self.group_member.is_active = False
        self.group_member.save()
        
        self.login_as(self.chairman)
        
        data = {
            'member': str(self.group_member.id),
            'amount': 50000.00,
            'purpose': 'Business loan',
            'loan_type': 'group_loan'
        }
        
        response = self.client.post(self.loans_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Member is not active', str(response.data))

    def test_member_cannot_create_loan(self):
        """Test regular member cannot create a loan"""
        self.login_as(self.member_user)
        
        data = {
            'member': str(self.group_member.id),
            'amount': 50000.00,
            'purpose': 'My loan',
            'loan_type': 'group_loan'
        }
        
        response = self.client.post(self.loans_list_url, data, format='json')
        
        # Should return 403 or 400
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])


class LoanApprovalTests(LoansBaseTest):
    """Tests for loan approval"""
    
    def test_chairman_can_approve_loan(self):
        """Test chairman can approve a pending loan"""
        self.login_as(self.chairman)
        
        # Create a pending loan
        loan = self._create_loan(status='pending')
        
        url = reverse('loan-approve', kwargs={'pk': str(loan.id)})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Loan approved successfully')
        
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'approved')
        self.assertIsNotNone(loan.approved_at)
        self.assertEqual(loan.approved_by, self.chairman)

    def test_cannot_approve_already_approved_loan(self):
        """Test cannot approve an already approved loan"""
        self.login_as(self.chairman)
        
        loan = self._create_loan(status='approved', approved_by=self.chairman, approved_at=timezone.now())
        
        url = reverse('loan-approve', kwargs={'pk': str(loan.id)})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Loan is not pending', str(response.data))

    def test_can_decline_loan(self):
        """Test can decline a pending loan"""
        self.login_as(self.chairman)
        
        loan = self._create_loan(status='pending')
        
        url = reverse('loan-decline', kwargs={'pk': str(loan.id)})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Loan declined successfully')
        
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'declined')


class LoanDisbursementTests(LoansBaseTest):
    """Tests for loan disbursement"""
    
    def test_admin_can_disburse_cash(self):
        """Test ECORET admin can disburse cash for ECORET loan"""
        self.login_as(self.admin)
        
        # Create an approved ECORET loan
        loan = self._create_loan(
            loan_type='ecoret_loan',
            status='approved',
            approved_by=self.admin,
            approved_at=timezone.now()
        )
        
        url = reverse('loan-disburse-cash', kwargs={'pk': str(loan.id)})
        data = {'receipt_number': 'RCP-001'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Loan disbursed via cash successfully')
        
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'disbursed')
        self.assertIsNotNone(loan.disbursed_at)
        self.assertEqual(loan.disbursement_method, 'cash')

    def test_chairman_can_disburse_cash_for_group_loan(self):
        """Test chairman can disburse cash for group loan"""
        self.login_as(self.chairman)
        
        # Create an approved group loan
        loan = self._create_loan(
            loan_type='group_loan',
            status='approved',
            approved_by=self.chairman,
            approved_at=timezone.now()
        )
        
        url = reverse('loan-chairman-disburse-cash', kwargs={'pk': str(loan.id)})
        data = {'receipt_number': 'RCP-002'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Cash disbursed', response.data['message'])
        
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'disbursed')
        self.assertEqual(loan.disbursement_method, 'cash')

    def test_chairman_can_disburse_bank_transfer(self):
        """Test chairman can disburse via bank transfer"""
        # Set member bank details
        self.group_member.bank_name = 'Test Bank'
        self.group_member.bank_account_name = 'Member Account'
        self.group_member.bank_account_number = '9876543210'
        self.group_member.save()
        
        self.login_as(self.chairman)
        
        loan = self._create_loan(
            loan_type='group_loan',
            status='approved',
            approved_by=self.chairman,
            approved_at=timezone.now()
        )
        
        url = reverse('loan-chairman-disburse-bank', kwargs={'pk': str(loan.id)})
        data = {'transfer_reference': 'TRF-001'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Bank transfer', response.data['message'])
        
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'disbursed')
        self.assertEqual(loan.disbursement_method, 'bank_transfer')


class LoanRepaymentTests(LoansBaseTest):
    """Tests for loan repayments"""
    
    def test_record_repayment(self):
        """Test recording a loan repayment"""
        self.login_as(self.chairman)
        
        # Create an active loan
        loan = self._create_loan(
            status='active',
            amount=100000.00,
            total_payable=110000.00
        )
        
        url = reverse('loan-record-repayment', kwargs={'pk': str(loan.id)})
        data = {'amount': 50000.00}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['principal_paid'], '50000.00')
        
        # Check loan balance
        balance = loan.get_balance()
        self.assertEqual(balance, 60000.00)  # 110000 - 50000

    def test_cannot_repay_more_than_balance(self):
        """Test cannot repay more than loan balance"""
        self.login_as(self.chairman)
        
        loan = self._create_loan(
            status='active',
            amount=50000.00,
            total_payable=55000.00
        )
        
        url = reverse('loan-record-repayment', kwargs={'pk': str(loan.id)})
        data = {'amount': 60000.00}  # More than balance
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds balance', str(response.data))

    def test_get_loan_balance(self):
        """Test getting loan balance"""
        self.login_as(self.chairman)
        
        loan = self._create_loan(
            status='active',
            amount=100000.00,
            total_payable=110000.00
        )
        
        # Make a repayment
        LoanRepayment.objects.create(
            loan=loan,
            member=loan.member,
            recorded_by=self.chairman,
            amount=30000.00,
            principal_paid=30000.00,
            interest_paid=0
        )
        
        url = reverse('loan-balance', kwargs={'pk': str(loan.id)})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_payable'], 110000.00)
        self.assertEqual(response.data['total_paid'], 30000.00)
        self.assertEqual(response.data['balance'], 80000.00)
        self.assertFalse(response.data['is_completed'])


class LoanRequestTests(LoansBaseTest):
    """Tests for ECORET loan requests"""
    
    def test_chairman_can_request_ecoret_loan(self):
        """Test chairman can request an ECORET loan"""
        self.login_as(self.chairman)
        
        data = {
            'amount': 100000.00,
            'purpose': 'Group project funding'
        }
        
        response = self.client.post(self.loan_requests_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['amount'], '100000.00')
        self.assertEqual(response.data['status'], 'pending')
        
        # Check activity log
        self.assertTrue(UserActivityLog.objects.filter(
            user=self.chairman,
            action='request_loan'
        ).exists())

    def test_member_cannot_request_ecoret_loan(self):
        """Test regular member cannot request ECORET loan"""
        self.login_as(self.member_user)
        
        data = {
            'amount': 100000.00,
            'purpose': 'My project'
        }
        
        response = self.client.post(self.loan_requests_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_approve_loan_request(self):
        """Test admin can approve an ECORET loan request"""
        self.login_as(self.admin)
        
        # Create a loan request
        loan_request = LoanRequest.objects.create(
            group=self.group,
            requested_by=self.chairman,
            amount=100000.00,
            purpose='Group project',
            status='pending'
        )
        
        url = reverse('loan-request-approve', kwargs={'pk': str(loan_request.id)})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Loan request approved. Loan is now ready for disbursement.')
        
        loan_request.refresh_from_db()
        self.assertEqual(loan_request.status, 'approved')
        
        # Check that a loan was created
        self.assertTrue(Loan.objects.filter(
            group=self.group,
            member__user=self.chairman,
            loan_type='ecoret_loan',
            amount=100000.00
        ).exists())


class LoanSettingsTests(LoansBaseTest):
    """Tests for loan settings"""
    
    def test_chairman_can_create_loan_settings(self):
        """Test chairman can create loan settings for their group"""
        self.login_as(self.chairman)
        
        # Delete existing settings first
        self.loan_settings.delete()
        
        data = {
            'default_interest_rate': 12.00,
            'group_loan_duration_months': 6,
            'ecoret_loan_duration_months': 12,
            'group_loan_min_amount': 1000.00,
            'group_loan_max_amount': 500000.00,
            'ecoret_loan_min_amount': 10000.00,
            'ecoret_loan_max_amount': 1000000.00,
            'requires_guarantor': True,
            'min_guarantors': 2,
            'grace_period_days': 7
        }
        
        response = self.client.post(self.loan_settings_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['default_interest_rate'], 12.00)

    def test_chairman_can_update_loan_settings(self):
        """Test chairman can update loan settings"""
        self.login_as(self.chairman)
        
        url = reverse('loan-settings-update-settings', kwargs={'pk': str(self.loan_settings.id)})
        data = {'default_interest_rate': 15.00}
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.loan_settings.refresh_from_db()
        self.assertEqual(self.loan_settings.default_interest_rate, 15.00)


class ECORETSettingsTests(LoansBaseTest):
    """Tests for ECORET settings"""
    
    def test_admin_can_view_ecoret_settings(self):
        """Test admin can view ECORET settings"""
        self.login_as(self.admin)
        
        response = self.client.get(self.ecoret_settings_list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_admin_can_update_ecoret_settings(self):
        """Test admin can update ECORET settings"""
        self.login_as(self.admin)
        
        url = reverse('ecoret-settings-detail', kwargs={'pk': str(self.ecoret_settings.id)})
        data = {'ecoret_loan_interest_rate': 15.00}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.ecoret_settings.refresh_from_db()
        self.assertEqual(self.ecoret_settings.ecoret_loan_interest_rate, 15.00)

    def test_chairman_cannot_view_ecoret_settings(self):
        """Test chairman cannot view ECORET settings"""
        self.login_as(self.chairman)
        
        response = self.client.get(self.ecoret_settings_list_url)
        
        # Should return 403 or empty list
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_200_OK])


class ECORETBankAccountTests(LoansBaseTest):
    """Tests for ECORET bank accounts"""
    
    def test_admin_can_create_bank_account(self):
        """Test admin can create an ECORET bank account"""
        self.login_as(self.admin)
        
        data = {
            'name': 'Secondary ECORET Account',
            'account_number': '0987654321',
            'bank_name': 'Standard Bank',
            'branch': 'City Branch',
            'balance': 500000.00,
            'status': 'active'
        }
        
        response = self.client.post(self.ecoret_accounts_list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Secondary ECORET Account')
        self.assertEqual(response.data['account_number'], '0987654321')

    def test_admin_can_set_default_account(self):
        """Test admin can set a default account"""
        self.login_as(self.admin)
        
        # Create a new account
        new_account = ECORETBankAccount.objects.create(
            name='New Primary Account',
            account_number='5555555555',
            bank_name='New Bank',
            branch='Main Branch',
            balance=2000000.00,
            status='active',
            is_default=False
        )
        
        url = reverse('ecoret-account-set-default', kwargs={'pk': str(new_account.id)})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], f'{new_account.name} set as default account successfully')
        
        # Check old account is no longer default
        self.ecoret_account.refresh_from_db()
        self.assertFalse(self.ecoret_account.is_default)
        
        new_account.refresh_from_db()
        self.assertTrue(new_account.is_default)

    def test_chairman_cannot_create_bank_account(self):
        """Test chairman cannot create ECORET bank account"""
        self.login_as(self.chairman)
        
        data = {
            'name': 'Chairman Account',
            'account_number': '1111111111',
            'bank_name': 'Chairman Bank',
            'branch': 'Chairman Branch',
            'balance': 100000.00,
            'status': 'active'
        }
        
        response = self.client.post(self.ecoret_accounts_list_url, data, format='json')
        
        # Should return 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)