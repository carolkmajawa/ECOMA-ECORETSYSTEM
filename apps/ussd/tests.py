from unittest.mock import patch
from django.test import TestCase
from apps.accounts.models import User
from apps.groups.models import Group, GroupMember
from apps.savings.models import Saving
from apps.ussd.models import USSDSession
from apps.ussd.views import USSDView


class USSDViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='member@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            phone_number='+265991234567',
        )
        self.group = Group.objects.create(
            group_name='Test Group',
            group_code='751400',
            is_active=True,
        )
        self.member = GroupMember.objects.create(
            group=self.group,
            user=self.user,
            full_name='Test User',
            national_id='1234567',
            phone_number='+265991234567',
        )
        self.session = USSDSession.objects.create(
            session_id='sess-1',
            phone_number='+265991234567',
            current_menu='welcome',
            language='en',
        )
        self.view = USSDView()

    def test_combined_language_and_group_code_input_opens_main_menu(self):
        response = self.view.handle_menu(self.session, ' 1*751400 ')

        self.assertIn('CON', response)
        self.assertIn('Take a Loan', response)
        self.assertIn('Deposit', response)
        self.assertEqual(self.session.group_code, '751400')
        self.session.refresh_from_db()
        self.assertEqual(self.session.group_code, '751400')
        self.assertEqual(self.session.member_id, self.member.id)

    @patch('apps.ussd.views.paychangu.initiate_payment')
    def test_full_path_savings_input_starts_mobile_money_payment(self, mock_initiate_payment):
        mock_initiate_payment.return_value = {
            'success': True,
            'reference': 'REF-123',
            'transaction_id': 'TX-123',
        }

        response = self.view.handle_menu(self.session, '2*751400*2*2*4000')

        self.assertIn('complete the payment', response.lower())
        self.assertEqual(self.session.current_menu, 'payment_pending')
        self.assertEqual(Saving.objects.count(), 0)

    @patch('apps.ussd.views.paychangu.initiate_payment')
    def test_savings_amount_starts_mobile_money_payment_and_confirms(self, mock_initiate_payment):
        mock_initiate_payment.return_value = {
            'success': True,
            'reference': 'REF-123',
            'transaction_id': 'TX-123',
        }

        self.session.group_code = '751400'
        self.session.member_id = self.member.id
        self.session.current_menu = 'savings_amount'
        self.session.save()

        response = self.view.handle_savings_amount(self.session, '751400', '500')

        self.assertIn('complete the payment', response.lower())
        self.assertEqual(self.session.current_menu, 'payment_pending')
        self.assertEqual(Saving.objects.count(), 0)

        confirmation_response = self.view.handle_menu(self.session, '1')

        self.assertIn('successfully', confirmation_response.lower())
        self.assertEqual(Saving.objects.count(), 1)
        self.assertEqual(Saving.objects.first().amount, 500)
