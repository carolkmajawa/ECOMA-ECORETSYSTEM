# """
# USSDView — complete file. Replace apps/ussd/views.py with this in full.
# """
# from decimal import Decimal
# import logging

# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import AllowAny
# from django.db.models import Q
# from django.utils import timezone

# from apps.groups.models import Group, GroupMember
# from apps.loans.models import Loan, LoanRepayment
# from apps.savings.models import Saving
# from apps.attendance.models import AttendanceCase, PenaltyPayment

# from .models import USSDSession
# from .languages import LanguageTranslations
# from .state_machine import state_machine
# from .services import loans as loan_module
# from .services.loans import LoanSettingsNotConfigured
# from .services.payments import payment_service, PaymentError
# from .services.logging_utils import log_safe

# logger = logging.getLogger(__name__)


# class USSDView(APIView):
#     permission_classes = [AllowAny]

#     def __init__(self):
#         self.translations = LanguageTranslations()

#     # ------------------------------------------------------------------
#     # Small unchanged helpers
#     # ------------------------------------------------------------------

#     def get_text(self, session, key, **kwargs):
#         language = getattr(session, 'language', 'en')
#         return self.translations.get_text(language, key, **kwargs)

#     def normalize_phone_number(self, phone):
#         import re
#         if not phone:
#             return phone
#         digits = re.sub(r'[^0-9]+', '', phone)
#         if len(digits) == 10 and digits.startswith('0'):
#             return f'+265{digits[1:]}'
#         if len(digits) == 9:
#             return f'+265{digits}'
#         if len(digits) > 0 and not phone.startswith('+'):
#             return f'+{digits}'
#         return f'+{digits}' if not phone.startswith('+') else phone

#     def phone_variants(self, phone):
#         variants = {phone or ''}
#         normalized = self.normalize_phone_number(phone)
#         variants.add(normalized)
#         if normalized and normalized.startswith('+'):
#             variants.add(normalized[1:])
#             variants.add(normalized.replace('+', ''))
#         return [v for v in variants if v]

#     def format_amount(self, amount):
#         amount = Decimal(amount)
#         if amount == amount.to_integral():
#             return f"{int(amount):,}"
#         return f"{amount:,.2f}"

#     # ------------------------------------------------------------------
#     # Entry point
#     # ------------------------------------------------------------------

#     def post(self, request):
#         data = request.data
#         phone_number = data.get('phoneNumber')
#         session_id = data.get('sessionId')
#         text = data.get('text', '')

#         log_safe("USSD request", phone_number=phone_number, text=text)

#         try:
#             session = self.get_or_create_session(session_id, phone_number)
#             if text == '':
#                 response = self.handle_welcome(session)
#             else:
#                 response = self.handle_menu(session, text)
#         except Exception:
#             logger.exception("Unhandled USSD error for session %s", session_id)
#             response = "END Sorry, something went wrong. Please try again."

#         return Response(response, content_type='text/plain')

#     def get_or_create_session(self, session_id, phone_number):
#         session, created = USSDSession.objects.get_or_create(
#             session_id=session_id,
#             defaults={'phone_number': phone_number, 'current_menu': 'welcome', 'language': 'en'},
#         )
#         if not created:
#             session.phone_number = phone_number
#             session.save()
#         return session

#     def reset_session_to_main(self, session):
#         session.current_menu = 'main'
#         session.loan_type = None
#         session.loan_amount = None
#         session.data = {}
#         session.save()
#         if session.group_code:
#             return self.get_main_menu(session, session.group_code)
#         return self.handle_welcome(session)

#     def handle_welcome(self, session):
#         session.current_menu = 'language'
#         session.save()
#         return f"""CON {self.get_text(session, 'welcome')}
# 1. English
# 2. Chichewa
# 0. {self.get_text(session, 'exit')}"""

#     # ------------------------------------------------------------------
#     # Menu navigation
#     #
#     # Levels 1 and 2 are inherently fixed (language, then group code) —
#     # there's no state to dispatch on yet because the session doesn't
#     # know who the subscriber is. From level 3 onward, EVERYTHING is
#     # driven by session.current_menu via state_machine.dispatch, never
#     # by counting '*'-separated tokens. A flow can grow or shrink by
#     # any number of steps without touching any other flow's handling.
#     # ------------------------------------------------------------------

#     def handle_menu(self, session, text):
#         raw_text = (text or '').strip()
#         parts = [p.strip() for p in raw_text.split('*') if p.strip()]
#         if not parts:
#             return self.handle_welcome(session)

#         if raw_text.endswith('00'):
#             if session.group_code and session.member_id:
#                 return self.reset_session_to_main(session)
#             return self.handle_welcome(session)

#         if raw_text == '0' or (raw_text.endswith('*0') and not raw_text.endswith('00')):
#             return self.handle_back(session)

#         level = len(parts)

#         if level == 1:
#             return self.handle_language_selection(session, parts[0])

#         if level == 2:
#             return self.handle_group_code_input(session, parts)

#         if not session.group_code or not session.member_id:
#             return self.get_group_code_prompt(session)

#         return state_machine.dispatch(self, session, session.group_code, parts[-1])

#     def handle_back(self, session):
#         """Where 'go back one step' lands, based purely on
#         session.current_menu — not on how many tokens were typed."""
#         menu = session.current_menu
#         group_code = session.group_code

#         if not group_code:
#             return self.handle_welcome(session)

#         transitions = {
#             'group_code': self.handle_welcome,
#             'main': lambda s: self.get_main_menu(s, group_code),
#             'loan_type_menu': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
#             'loan_amount': lambda s: self._enter_menu(s, 'loan_type_menu', self.get_loan_type_menu, group_code),
#             'otp_verification': lambda s: self._enter_menu(s, 'loan_amount', self.get_loan_amount_prompt, group_code),
#             'deposit_menu': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
#             'repayment_amount': lambda s: self._enter_menu(s, 'deposit_menu', self.get_deposit_menu, group_code),
#             'savings_amount': lambda s: self._enter_menu(s, 'deposit_menu', self.get_deposit_menu, group_code),
#             'balance_menu': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
#             'cases_list': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
#             'payment_pending': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
#         }
#         handler = transitions.get(menu, lambda s: self.get_main_menu(s, group_code))
#         return handler(session)

#     def handle_language_selection(self, session, choice):
#         if choice == '1':
#             session.language = 'en'
#         elif choice == '2':
#             session.language = 'ny'
#         elif choice == '0':
#             return self.handle_exit(session)
#         else:
#             return self.handle_invalid(session)
#         session.current_menu = 'group_code'
#         session.group_code = None
#         session.member_id = None
#         session.group_id = None
#         session.loan_type = None
#         session.loan_amount = None
#         session.data = {}
#         session.save()
#         return self.get_group_code_prompt(session)

#     def handle_group_code_input(self, session, parts):
#         if parts[0] == '1' and parts[1].isdigit():
#             return self.handle_group_code(session, parts[1])
#         if parts[0] == '0':
#             return self.handle_welcome(session)
#         session.current_menu = 'group_code'
#         session.save()
#         return f"END {self.get_text(session, 'invalid_group')}"

#     def handle_group_code(self, session, group_code):
#         try:
#             group = Group.objects.get(group_code=group_code, is_active=True)
#         except Group.DoesNotExist:
#             log_safe("Group code not found", level='warning', group_code=group_code)
#             session.current_menu = 'group_code'
#             session.group_code = None
#             session.member_id = None
#             session.save()
#             return f"END {self.get_text(session, 'invalid_group')}"

#         phone_values = self.phone_variants(session.phone_number)
#         member = GroupMember.objects.filter(group=group, is_active=True).filter(
#             Q(phone_number__in=phone_values) | Q(user__phone_number__in=phone_values)
#         ).first()

#         if not member:
#             session.current_menu = 'group_code'
#             session.group_code = None
#             session.member_id = None
#             session.save()
#             return f"END {self.get_text(session, 'not_registered')}"

#         session.group_code = group_code
#         session.group_id = group.id
#         session.member_id = member.id
#         session.current_menu = 'main'
#         session.loan_type = None
#         session.loan_amount = None
#         session.data = {}
#         session.save()
#         return self.get_main_menu(session, group_code)

#     def get_group_code_prompt(self, session):
#         return f"""CON {self.get_text(session, 'enter_group_code')}
# 0. {self.get_text(session, 'back')}"""

#     # ------------------------------------------------------------------
#     # Main menu + sub-menus (states registered in state_machine.py)
#     # ------------------------------------------------------------------

#     def get_main_menu(self, session, group_code):
#         try:
#             member = GroupMember.objects.get(id=session.member_id)
#         except GroupMember.DoesNotExist:
#             return self.handle_exit(session)

#         session.current_menu = 'main'
#         session.save()
#         return f"""CON {self.get_text(session, 'main_menu', name=member.full_name)}
# 1. {self.get_text(session, 'take_loan')}
# 2. {self.get_text(session, 'deposit')}
# 3. {self.get_text(session, 'check_balance')}
# 4. {self.get_text(session, 'my_info')}
# 5. View Case Penalties
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'exit')}"""

#     def handle_main_menu_choice(self, session, group_code, choice):
#         if choice == '1':
#             session.current_menu = 'loan_type_menu'
#             session.save()
#             return self.get_loan_type_menu(session, group_code)
#         if choice == '2':
#             return self._enter_menu(session, 'deposit_menu', self.get_deposit_menu, group_code)
#         if choice == '3':
#             return self._enter_menu(session, 'balance_menu', self.get_balance_menu, group_code)
#         if choice == '4':
#             return self.handle_my_info(session, group_code)
#         if choice == '5':
#             return self.handle_view_cases(session, group_code)
#         if choice == '0':
#             return self.handle_exit(session)
#         return self.handle_invalid(session)

#     def _enter_menu(self, session, menu_name, builder, group_code):
#         session.current_menu = menu_name
#         session.save()
#         return builder(session, group_code)

#     def get_loan_type_menu(self, session, group_code):
#         return f"""CON {self.get_text(session, 'take_loan')}
# 1. {self.get_text(session, 'group_loan')}
# 2. {self.get_text(session, 'ecoret_loan')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def handle_loan_type_choice(self, session, group_code, choice):
#         if choice in ('1', '2'):
#             session.loan_type = 'group_loan' if choice == '1' else 'ecoret_loan'
#             return self._enter_menu(session, 'loan_amount', self.get_loan_amount_prompt, group_code)
#         return self.handle_invalid(session)

#     def get_loan_amount_prompt(self, session, group_code):
#         try:
#             group = Group.objects.get(group_code=group_code)
#             min_amount, max_amount, _rate, _duration = loan_module.get_loan_terms(
#                 group, session.loan_type or 'group_loan'
#             )
#         except (Group.DoesNotExist, LoanSettingsNotConfigured) as exc:
#             return f"END {exc}" if isinstance(exc, LoanSettingsNotConfigured) else self.handle_invalid(session)

#         return f"""CON {self.get_text(session, 'loan_amount')}
# {self.get_text(session, 'min_amount', amount=self.format_amount(min_amount))}
# {self.get_text(session, 'max_amount', amount=self.format_amount(max_amount))}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def get_deposit_menu(self, session, group_code):
#         return f"""CON {self.get_text(session, 'deposit_options')}
# 1. {self.get_text(session, 'repay_loan')}
# 2. {self.get_text(session, 'pay_savings')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def handle_deposit_menu_choice(self, session, group_code, choice):
#         if choice == '1':
#             return self._enter_menu(session, 'repayment_amount', self.get_repayment_amount_prompt, group_code)
#         if choice == '2':
#             return self._enter_menu(session, 'savings_amount', self.get_savings_amount_prompt, group_code)
#         return self.handle_invalid(session)

#     def get_balance_menu(self, session, group_code):
#         return f"""CON {self.get_text(session, 'balance_options')}
# 1. {self.get_text(session, 'loan_balance')}
# 2. {self.get_text(session, 'savings_balance')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def handle_balance_menu_choice(self, session, group_code, choice):
#         if choice == '1':
#             return self.handle_loan_balance(session, group_code)
#         if choice == '2':
#             return self.handle_savings_balance(session, group_code)
#         return self.handle_invalid(session)

#     def get_repayment_amount_prompt(self, session, group_code):
#         return f"""CON {self.get_text(session, 'repayment_amount')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def get_savings_amount_prompt(self, session, group_code):
#         return f"""CON {self.get_text(session, 'savings_amount')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def get_invalid_amount_prompt(self, session, group_code):
#         return f"""CON {self.get_text(session, 'invalid_amount')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def get_payment_pending_prompt(self, session):
#         return f"""CON {self.get_text(session, 'payment_pending')}
# 1. Confirm payment
# 0. {self.get_text(session, 'back')}"""

#     def handle_view_cases(self, session, group_code):
#         try:
#             member = GroupMember.objects.get(id=session.member_id)
#         except GroupMember.DoesNotExist:
#             return self.handle_invalid(session)

#         unpaid_cases = AttendanceCase.objects.filter(member=member, status='pending').order_by('created_at')[:5]

#         if not unpaid_cases.exists():
#             session.current_menu = 'main'
#             session.save()
#             return f"END You have no unpaid case penalties.\n{self.get_text(session, 'thank_you')}"

#         message = "Your Case Penalties:\n"
#         for i, case in enumerate(unpaid_cases, start=1):
#             case_date = case.meeting_date.strftime('%Y-%m-%d') if case.meeting_date else case.created_at.strftime('%Y-%m-%d')
#             balance = case.penalty_amount - case.penalty_paid
#             message += f"{i}. Case: {case_date} - MK{self.format_amount(balance)}\n"
#             session.data[f'case_{i}_id'] = str(case.id)

#         message += "\nEnter case number to pay (1-5) or 0 to go back"
#         session.current_menu = 'cases_list'
#         session.save()
#         return f"CON {message}\n0. Back"

#     def handle_my_info(self, session, group_code):
#         member = GroupMember.objects.get(id=session.member_id)
#         return f"""END {self.get_text(session, 'member_info')}
# {self.get_text(session, 'name')}: {member.full_name}
# {self.get_text(session, 'phone')}: {member.phone_number}
# {self.get_text(session, 'group')}: {member.group.group_name}
# {self.get_text(session, 'member_since')} {member.joined_date.strftime('%Y-%m-%d')}
# {self.get_text(session, 'thank_you')}"""

#     def handle_loan_balance(self, session, group_code):
#         member = GroupMember.objects.get(id=session.member_id)
#         loans = Loan.objects.filter(member=member, status__in=['active', 'approved'])
#         if not loans.exists():
#             return f"END {self.get_text(session, 'no_active_loans')}"

#         total_balance = 0
#         message = f"{self.get_text(session, 'loan_balance')}:\n"
#         for loan in loans:
#             balance = loan.get_balance()
#             total_balance += balance
#             message += f"- MK{loan.amount:,.2f}: MK{balance:,.2f}\n"
#         message += f"\n{self.get_text(session, 'total_balance')} MK{total_balance:,.2f}"
#         return f"END {message}\n{self.get_text(session, 'thank_you')}"

#     def handle_savings_balance(self, session, group_code):
#         from django.db.models import Sum
#         member = GroupMember.objects.get(id=session.member_id)
#         savings = Saving.objects.filter(member=member)
#         total_deposits = savings.filter(transaction_type='deposit').aggregate(total=Sum('amount'))['total'] or 0
#         total_withdrawals = savings.filter(transaction_type='withdrawal').aggregate(total=Sum('amount'))['total'] or 0
#         balance = total_deposits - total_withdrawals
#         return f"""END {self.get_text(session, 'savings_balance')}:
# {self.get_text(session, 'total_deposits')} MK{total_deposits:,.2f}
# {self.get_text(session, 'total_withdrawals')} MK{total_withdrawals:,.2f}
# {self.get_text(session, 'total_balance')} MK{balance:,.2f}
# {self.get_text(session, 'thank_you')}"""

#     def handle_exit(self, session=None):
#         thank_you = self.get_text(session, 'thank_you') if session else 'Thank you'
#         return f"END {thank_you}"

#     def handle_invalid(self, session):
#         return f"END {self.get_text(session, 'invalid_option')}"

#     # ------------------------------------------------------------------
#     # Loan flow — terms fetched directly from apps.loans.models.LoanSettings
#     # ------------------------------------------------------------------

#     def process_loan_amount(self, session, group_code, amount):
#         try:
#             group = Group.objects.get(group_code=group_code)
#         except Group.DoesNotExist:
#             log_safe("Group missing during loan amount entry", level='warning', group_code=group_code)
#             return self.handle_invalid(session)

#         loan_type = session.loan_type or 'group_loan'

#         try:
#             min_amount, max_amount, interest_rate, duration_months = loan_module.get_loan_terms(group, loan_type)
#         except LoanSettingsNotConfigured as exc:
#             return f"END {exc}"

#         if not (min_amount <= amount <= max_amount):
#             return self.get_invalid_amount_prompt(session, group_code)

#         total_payable = loan_module.calculate_total_payable(amount, interest_rate)
#         session.data['interest_rate'] = str(interest_rate)
#         session.data['duration_months'] = duration_months
#         session.data['total_payable'] = str(total_payable)
#         session.loan_amount = amount
#         session.current_menu = 'otp_verification'
#         session.save()

#         try:
#             member = GroupMember.objects.get(id=session.member_id)
#         except GroupMember.DoesNotExist:
#             log_safe("Member missing during loan OTP issue", level='error', member_id=session.member_id)
#             return self.handle_invalid(session)

#         otp_code, correlation_id = loan_module.issue_loan_otp(
#             phone_number=session.phone_number,
#             member_id=session.member_id,
#             amount=amount,
#             loan_type=loan_type,
#         )
#         self._send_otp_sms(member, otp_code)

#         return f"""CON Loan Summary:
# Amount: MK{self.format_amount(amount)}
# Interest Rate: {session.data['interest_rate']}%
# Total Payable: MK{self.format_amount(total_payable)}

# {self.get_text(session, 'enter_otp')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#     def _send_otp_sms(self, member, otp_code):
#         try:
#             from apps.notifications.services import NotificationService
#             notification = NotificationService()
#             recipients = [r for r in (member.user, getattr(member.group, 'secretary', None)) if r]
#             for recipient in recipients:
#                 notification.send_sms_notification(recipient, f'ECORET: Your loan OTP is: {otp_code}')
#         except Exception:
#             logger.exception("Failed to send loan OTP SMS to member %s", member.id)

#     def handle_otp_verification(self, session, group_code, otp_code):
#         record = loan_module.verify_loan_otp(phone_number=session.phone_number, otp_code=otp_code)
#         if not record:
#             return f"""CON {self.get_text(session, 'otp_invalid')}
# {self.get_text(session, 'enter_otp')}
# 0. {self.get_text(session, 'back')}
# 00. {self.get_text(session, 'main_menu')}"""

#         loan_request = loan_module.get_pending_loan_request(
#             member_id=session.member_id, correlation_id=record.correlation_id
#         )
#         if not loan_request:
#             return self.handle_invalid(session)

#         loan_request.status = 'pending_approval'
#         loan_request.save()

#         try:
#             member = GroupMember.objects.get(id=session.member_id)
#             chairman = member.group.chairman
#             if chairman:
#                 from apps.notifications.services import NotificationService
#                 NotificationService().send_notification(
#                     chairman,
#                     f'New {loan_request.loan_type} Loan Request',
#                     f'{member.full_name} requested a loan of MK{loan_request.amount} via USSD.',
#                     'loan_request',
#                     {'loan_id': str(loan_request.id)},
#                 )
#         except Exception:
#             logger.exception("Failed to notify chairman of loan request %s", loan_request.id)

#         session.current_menu = 'main'
#         session.loan_amount = None
#         session.loan_type = None
#         session.save()

#         return f"""END Loan request submitted!
# Amount: MK{loan_request.amount:,.2f}
# Interest Rate: {session.data.get('interest_rate', 'N/A')}%
# Total Payable: MK{self.format_amount(session.data.get('total_payable', 0))}
# You will be notified once approved.
# {self.get_text(session, 'thank_you')}"""

#     # ------------------------------------------------------------------
#     # Deposits — thin wrappers around payment_service
#     # ------------------------------------------------------------------

#     def handle_repayment_amount(self, session, group_code, amount):
#         try:
#             member = GroupMember.objects.get(id=session.member_id)
#         except GroupMember.DoesNotExist:
#             return self.handle_invalid(session)

#         loan = Loan.objects.filter(member=member, status='active').first()
#         if not loan:
#             return f"END {self.get_text(session, 'no_active_loans')}"

#         return self._start_payment(session, member, amount, 'repayment', {'loan_id': str(loan.id)})

#     def handle_savings_amount(self, session, group_code, amount):
#         try:
#             member = GroupMember.objects.get(id=session.member_id)
#         except GroupMember.DoesNotExist:
#             return self.handle_invalid(session)
#         return self._start_payment(session, member, amount, 'savings', {'group_id': str(session.group_id)})

#     def select_case_for_payment(self, session, group_code, case_index):
#         case_id = session.data.get(f'case_{case_index}_id')
#         if not case_id:
#             return self.handle_invalid(session)

#         try:
#             case = AttendanceCase.objects.get(id=case_id, status='pending')
#             member = GroupMember.objects.get(id=session.member_id)
#         except (AttendanceCase.DoesNotExist, GroupMember.DoesNotExist):
#             return "END This case has already been paid or does not exist."

#         balance = case.penalty_amount - case.penalty_paid
#         return self._start_payment(session, member, balance, 'case_penalty', {'case_id': str(case.id)})

#     def _start_payment(self, session, member, amount, payment_type, payload):
#         try:
#             result = payment_service.start_stk_push(member=member, amount=amount, payment_type=payment_type, payload=payload)
#         except PaymentError:
#             return "END Payment could not be started. Please try again later."

#         session.current_menu = 'payment_pending'
#         session.data['payment_type'] = payment_type
#         session.data['payment_amount'] = str(amount)
#         session.data['payment_reference'] = result['reference']
#         session.data['payment_payload'] = result['payload']
#         session.save()
#         return self.get_payment_pending_prompt(session)

#     def complete_pending_mobile_payment(self, session):
#         payment_type = session.data.get('payment_type')
#         reference = session.data.get('payment_reference')
#         payload = session.data.get('payment_payload', {})

#         try:
#             amount = int(session.data.get('payment_amount', 0))
#             member = GroupMember.objects.get(id=session.member_id)
#         except (ValueError, GroupMember.DoesNotExist):
#             return "END Payment could not be completed. Please try again later."

#         handlers = {
#             'repayment': self._complete_repayment,
#             'savings': self._complete_savings,
#             'case_penalty': self._complete_case_penalty,
#         }
#         handler = handlers.get(payment_type)
#         if not handler:
#             return self.handle_invalid(session)

#         try:
#             message = handler(member, amount, reference, payload)
#         except Exception:
#             logger.exception("Payment completion failed for reference %s", reference)
#             return "END Payment could not be completed. Please try again later."

#         payment_service.mark_transaction_success(member=member, reference=reference)
#         session.current_menu = 'main'
#         session.save()
#         return f"END {message}"

#     def _complete_repayment(self, member, amount, reference, payload):
#         loan = Loan.objects.get(id=payload.get('loan_id'))
#         LoanRepayment.objects.create(
#             loan=loan, member=member, amount=amount, principal_paid=amount,
#             interest_paid=0, payment_method='mobile_money', transaction_reference=reference,
#         )
#         payment_service.record_audit(member=member, transaction_type='loan_repayment', amount=amount, reference=reference)
#         return "Payment completed successfully. Your repayment has been recorded."

#     def _complete_savings(self, member, amount, reference, payload):
#         Saving.objects.create(
#             group=member.group, member=member, amount=amount, saving_type='voluntary',
#             transaction_type='deposit', reference_number=reference,
#             notes='USSD Mobile Money Deposit',
#         )
#         payment_service.record_audit(member=member, transaction_type='savings_deposit', amount=amount, reference=reference)
#         return "Payment completed successfully. Your savings deposit has been recorded."

#     def _complete_case_penalty(self, member, amount, reference, payload):
#         case_id = payload.get('case_id')
#         case = AttendanceCase.objects.get(id=case_id)
#         case.penalty_paid += Decimal(str(amount))
#         if case.penalty_paid >= case.penalty_amount:
#             case.status = 'resolved'
#             case.resolved_by = member.user
#             case.resolved_at = timezone.now()
#         case.save()

#         PenaltyPayment.objects.create(
#             attendance_case=case, member=member, amount=Decimal(str(amount)),
#             payment_method='mobile_money', transaction_reference=reference,
#             recorded_by=member.user,
#         )
#         payment_service.record_audit(
#             member=member, transaction_type='case_penalty_payment', amount=amount,
#             reference=reference, details={'case_id': str(case_id), 'payment_reference': reference},
#         )
#         return "Payment completed successfully. Your case penalty has been paid."

"""
USSDView — complete file. Replace apps/ussd/views.py with this in full.
"""
from decimal import Decimal
import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Q
from django.utils import timezone

from apps.groups.models import Group, GroupMember
from apps.loans.models import Loan, LoanRepayment
from apps.savings.models import Saving
from apps.attendance.models import AttendanceCase, PenaltyPayment

from .models import USSDSession
from .languages import LanguageTranslations
from .state_machine import state_machine
from .services import loans as loan_module
from .services.loans import LoanSettingsNotConfigured
from .services.payments import payment_service, PaymentError
from .services.logging_utils import log_safe

logger = logging.getLogger(__name__)


class USSDView(APIView):
    permission_classes = [AllowAny]

    def __init__(self):
        self.translations = LanguageTranslations()

    # ------------------------------------------------------------------
    # Small unchanged helpers
    # ------------------------------------------------------------------

    def get_text(self, session, key, **kwargs):
        language = getattr(session, 'language', 'en')
        return self.translations.get_text(language, key, **kwargs)

    def normalize_phone_number(self, phone):
        import re
        if not phone:
            return phone
        digits = re.sub(r'[^0-9]+', '', phone)
        if len(digits) == 10 and digits.startswith('0'):
            return f'+265{digits[1:]}'
        if len(digits) == 9:
            return f'+265{digits}'
        if len(digits) > 0 and not phone.startswith('+'):
            return f'+{digits}'
        return f'+{digits}' if not phone.startswith('+') else phone

    def phone_variants(self, phone):
        variants = {phone or ''}
        normalized = self.normalize_phone_number(phone)
        variants.add(normalized)
        if normalized and normalized.startswith('+'):
            variants.add(normalized[1:])
            variants.add(normalized.replace('+', ''))
        return [v for v in variants if v]

    def _main_menu_label(self, session):
        """Label for the '00.' shortcut shown on every sub-screen.
        Deliberately NOT the same translation key as the main-menu
        banner (get_text(session, 'main_menu', name=...)), which is a
        'Welcome {name}' template -- reusing that key here was
        rendering literal 'Welcome {name}' next to '00.' since no name
        was supplied. TODO: fold this into apps/ussd/languages.py as
        its own key once you confirm the Chichewa wording.
        """
        language = getattr(session, 'language', 'en')
        return 'Main Menu' if language == 'en' else 'Main Menu'  # TODO: Chichewa wording

    def format_amount(self, amount):
        amount = Decimal(amount)
        if amount == amount.to_integral():
            return f"{int(amount):,}"
        return f"{amount:,.2f}"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def post(self, request):
        data = request.data
        phone_number = data.get('phoneNumber')
        session_id = data.get('sessionId')
        text = data.get('text', '')

        log_safe("USSD request", phone_number=phone_number, text=text)

        try:
            session = self.get_or_create_session(session_id, phone_number)
            if text == '':
                response = self.handle_welcome(session)
            else:
                response = self.handle_menu(session, text)
        except Exception:
            logger.exception("Unhandled USSD error for session %s", session_id)
            response = "END Sorry, something went wrong. Please try again."

        return Response(response, content_type='text/plain')

    def get_or_create_session(self, session_id, phone_number):
        session, created = USSDSession.objects.get_or_create(
            session_id=session_id,
            defaults={'phone_number': phone_number, 'current_menu': 'welcome', 'language': 'en'},
        )
        if not created:
            session.phone_number = phone_number
            session.save()
        return session

    def reset_session_to_main(self, session):
        session.current_menu = 'main'
        session.loan_type = None
        session.loan_amount = None
        session.data = {}
        session.save()
        if session.group_code:
            return self.get_main_menu(session, session.group_code)
        return self.handle_welcome(session)

    def handle_welcome(self, session):
        session.current_menu = 'language'
        session.save()
        return f"""CON {self.get_text(session, 'welcome')}
1. English
2. Chichewa
0. {self.get_text(session, 'exit')}"""

    # ------------------------------------------------------------------
    # Menu navigation
    #
    # Levels 1 and 2 are inherently fixed (language, then group code) —
    # there's no state to dispatch on yet because the session doesn't
    # know who the subscriber is. From level 3 onward, EVERYTHING is
    # driven by session.current_menu via state_machine.dispatch, never
    # by counting '*'-separated tokens. A flow can grow or shrink by
    # any number of steps without touching any other flow's handling.
    # ------------------------------------------------------------------

    def handle_menu(self, session, text):
        raw_text = (text or '').strip()
        parts = [p.strip() for p in raw_text.split('*') if p.strip()]
        if not parts:
            return self.handle_welcome(session)

        level = len(parts)

        if level == 1:
            return self.handle_language_selection(session, parts[0])

        if level == 2:
            return self.handle_group_code_input(session, parts)

        # From here on, '0'/'00' are universal shortcuts -- but checked
        # against the LAST TOKEN the subscriber typed, never against
        # the raw accumulated string. Checking raw_text.endswith('00')
        # was matching amounts like 20000, 5000, 100 (which legitimately
        # end in the characters '00'), silently bouncing the user back
        # to the main menu instead of processing their amount.
        last_token = parts[-1]

        if last_token == '00':
            if session.group_code and session.member_id:
                return self.reset_session_to_main(session)
            return self.handle_welcome(session)

        if last_token == '0':
            return self.handle_back(session)

        if not session.group_code or not session.member_id:
            return self.get_group_code_prompt(session)

        return state_machine.dispatch(self, session, session.group_code, last_token)

    def handle_back(self, session):
        """Where 'go back one step' lands, based purely on
        session.current_menu — not on how many tokens were typed."""
        menu = session.current_menu
        group_code = session.group_code

        if not group_code:
            return self.handle_welcome(session)

        transitions = {
            'group_code': self.handle_welcome,
            'main': lambda s: self.get_main_menu(s, group_code),
            'loan_type_menu': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
            'loan_amount': lambda s: self._enter_menu(s, 'loan_type_menu', self.get_loan_type_menu, group_code),
            'otp_verification': lambda s: self._enter_menu(s, 'loan_amount', self.get_loan_amount_prompt, group_code),
            'deposit_menu': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
            'repayment_amount': lambda s: self._enter_menu(s, 'deposit_menu', self.get_deposit_menu, group_code),
            'savings_amount': lambda s: self._enter_menu(s, 'deposit_menu', self.get_deposit_menu, group_code),
            'balance_menu': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
            'cases_list': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
            'payment_pending': lambda s: self._enter_menu(s, 'main', self.get_main_menu, group_code),
        }
        handler = transitions.get(menu, lambda s: self.get_main_menu(s, group_code))
        return handler(session)

    def handle_language_selection(self, session, choice):
        if choice == '1':
            session.language = 'en'
        elif choice == '2':
            session.language = 'ny'
        elif choice == '0':
            return self.handle_exit(session)
        else:
            return self.handle_invalid(session)
        session.current_menu = 'group_code'
        session.group_code = None
        session.member_id = None
        session.group_id = None
        session.loan_type = None
        session.loan_amount = None
        session.data = {}
        session.save()
        return self.get_group_code_prompt(session)

    def handle_group_code_input(self, session, parts):
        if parts[0] in ('1', '2') and parts[1].isdigit():
            # Record the language choice here too, in case this is a
            # fresh session where language + group code arrived in one
            # combined request rather than two separate ones. The old
            # check only ever accepted parts[0] == '1' (English), which
            # is why selecting Chichewa ('2') always fell through to
            # "invalid group" regardless of whether the code was right.
            session.language = 'en' if parts[0] == '1' else 'ny'
            return self.handle_group_code(session, parts[1])
        if parts[0] == '0':
            return self.handle_welcome(session)
        session.current_menu = 'group_code'
        session.save()
        return f"END {self.get_text(session, 'invalid_group')}"

    def handle_group_code(self, session, group_code):
        try:
            group = Group.objects.get(group_code=group_code, is_active=True)
        except Group.DoesNotExist:
            log_safe("Group code not found", level='warning', group_code=group_code)
            session.current_menu = 'group_code'
            session.group_code = None
            session.member_id = None
            session.save()
            return f"END {self.get_text(session, 'invalid_group')}"

        phone_values = self.phone_variants(session.phone_number)
        member = GroupMember.objects.filter(group=group, is_active=True).filter(
            Q(phone_number__in=phone_values) | Q(user__phone_number__in=phone_values)
        ).first()

        if not member:
            session.current_menu = 'group_code'
            session.group_code = None
            session.member_id = None
            session.save()
            return f"END {self.get_text(session, 'not_registered')}"

        session.group_code = group_code
        session.group_id = group.id
        session.member_id = member.id
        session.current_menu = 'main'
        session.loan_type = None
        session.loan_amount = None
        session.data = {}
        session.save()
        return self.get_main_menu(session, group_code)

    def get_group_code_prompt(self, session):
        return f"""CON {self.get_text(session, 'enter_group_code')}
0. {self.get_text(session, 'back')}"""

    # ------------------------------------------------------------------
    # Main menu + sub-menus (states registered in state_machine.py)
    # ------------------------------------------------------------------

    def get_main_menu(self, session, group_code):
        try:
            member = GroupMember.objects.get(id=session.member_id)
        except GroupMember.DoesNotExist:
            return self.handle_exit(session)

        session.current_menu = 'main'
        session.save()
        return f"""CON {self.get_text(session, 'main_menu', name=member.full_name)}
1. {self.get_text(session, 'take_loan')}
2. {self.get_text(session, 'deposit')}
3. {self.get_text(session, 'check_balance')}
4. {self.get_text(session, 'my_info')}
5. View Case Penalties
0. {self.get_text(session, 'back')}
00. {self.get_text(session, 'exit')}"""

    def handle_main_menu_choice(self, session, group_code, choice):
        if choice == '1':
            session.current_menu = 'loan_type_menu'
            session.save()
            return self.get_loan_type_menu(session, group_code)
        if choice == '2':
            return self._enter_menu(session, 'deposit_menu', self.get_deposit_menu, group_code)
        if choice == '3':
            return self._enter_menu(session, 'balance_menu', self.get_balance_menu, group_code)
        if choice == '4':
            return self.handle_my_info(session, group_code)
        if choice == '5':
            return self.handle_view_cases(session, group_code)
        if choice == '0':
            return self.handle_exit(session)
        return self.handle_invalid(session)

    def _enter_menu(self, session, menu_name, builder, group_code):
        session.current_menu = menu_name
        session.save()
        return builder(session, group_code)

    def get_loan_type_menu(self, session, group_code):
        return f"""CON {self.get_text(session, 'take_loan')}
1. {self.get_text(session, 'group_loan')}
2. {self.get_text(session, 'ecoret_loan')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def handle_loan_type_choice(self, session, group_code, choice):
        if choice in ('1', '2'):
            session.loan_type = 'group_loan' if choice == '1' else 'ecoret_loan'
            return self._enter_menu(session, 'loan_amount', self.get_loan_amount_prompt, group_code)
        return self.handle_invalid(session)

    def get_loan_amount_prompt(self, session, group_code):
        try:
            group = Group.objects.get(group_code=group_code)
            min_amount, max_amount, _rate, _duration = loan_module.get_loan_terms(
                group, session.loan_type or 'group_loan'
            )
        except (Group.DoesNotExist, LoanSettingsNotConfigured) as exc:
            return f"END {exc}" if isinstance(exc, LoanSettingsNotConfigured) else self.handle_invalid(session)

        return f"""CON {self.get_text(session, 'loan_amount')}
{self.get_text(session, 'min_amount', amount=self.format_amount(min_amount))}
{self.get_text(session, 'max_amount', amount=self.format_amount(max_amount))}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def get_deposit_menu(self, session, group_code):
        return f"""CON {self.get_text(session, 'deposit_options')}
1. {self.get_text(session, 'repay_loan')}
2. {self.get_text(session, 'pay_savings')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def handle_deposit_menu_choice(self, session, group_code, choice):
        if choice == '1':
            return self._enter_menu(session, 'repayment_amount', self.get_repayment_amount_prompt, group_code)
        if choice == '2':
            return self._enter_menu(session, 'savings_amount', self.get_savings_amount_prompt, group_code)
        return self.handle_invalid(session)

    def get_balance_menu(self, session, group_code):
        return f"""CON {self.get_text(session, 'balance_options')}
1. {self.get_text(session, 'loan_balance')}
2. {self.get_text(session, 'savings_balance')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def handle_balance_menu_choice(self, session, group_code, choice):
        if choice == '1':
            return self.handle_loan_balance(session, group_code)
        if choice == '2':
            return self.handle_savings_balance(session, group_code)
        return self.handle_invalid(session)

    def get_repayment_amount_prompt(self, session, group_code):
        balance_line = ''
        try:
            member = GroupMember.objects.get(id=session.member_id)
            loan = Loan.objects.filter(member=member, status='active').first()
            if loan:
                balance_line = f"You have MK{self.format_amount(loan.get_balance())} loan to repay.\n"
        except GroupMember.DoesNotExist:
            pass

        return f"""CON {balance_line}{self.get_text(session, 'repayment_amount')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def get_savings_amount_prompt(self, session, group_code):
        return f"""CON {self.get_text(session, 'savings_amount')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def get_invalid_amount_prompt(self, session, group_code):
        return f"""CON {self.get_text(session, 'invalid_amount')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def get_payment_pending_prompt(self, session):
        return f"""CON {self.get_text(session, 'payment_pending')}
1. Confirm payment
0. {self.get_text(session, 'back')}"""

    def handle_view_cases(self, session, group_code):
        try:
            member = GroupMember.objects.get(id=session.member_id)
        except GroupMember.DoesNotExist:
            return self.handle_invalid(session)

        unpaid_cases = AttendanceCase.objects.filter(member=member, status='pending').order_by('created_at')[:5]

        if not unpaid_cases.exists():
            session.current_menu = 'main'
            session.save()
            return f"END You have no unpaid case penalties.\n{self.get_text(session, 'thank_you')}"

        message = "Your Case Penalties:\n"
        for i, case in enumerate(unpaid_cases, start=1):
            case_date = case.meeting_date.strftime('%Y-%m-%d') if case.meeting_date else case.created_at.strftime('%Y-%m-%d')
            balance = case.penalty_amount - case.penalty_paid
            message += f"{i}. Case: {case_date} - MK{self.format_amount(balance)}\n"
            session.data[f'case_{i}_id'] = str(case.id)

        message += "\nEnter case number to pay (1-5) or 0 to go back"
        session.current_menu = 'cases_list'
        session.save()
        return f"CON {message}\n0. Back"

    def handle_my_info(self, session, group_code):
        member = GroupMember.objects.get(id=session.member_id)
        return f"""END {self.get_text(session, 'member_info')}
{self.get_text(session, 'name')}: {member.full_name}
{self.get_text(session, 'phone')}: {member.phone_number}
{self.get_text(session, 'group')}: {member.group.group_name}
{self.get_text(session, 'member_since')} {member.joined_date.strftime('%Y-%m-%d')}
{self.get_text(session, 'thank_you')}"""

    def handle_loan_balance(self, session, group_code):
        member = GroupMember.objects.get(id=session.member_id)
        loans = Loan.objects.filter(member=member, status__in=['active', 'approved'])
        if not loans.exists():
            return f"END {self.get_text(session, 'no_active_loans')}"

        total_balance = 0
        message = f"{self.get_text(session, 'loan_balance')}:\n"
        for loan in loans:
            balance = loan.get_balance()
            total_balance += balance
            message += f"- MK{loan.amount:,.2f}: MK{balance:,.2f}\n"
        message += f"\n{self.get_text(session, 'total_balance')} MK{total_balance:,.2f}"
        return f"END {message}\n{self.get_text(session, 'thank_you')}"

    def handle_savings_balance(self, session, group_code):
        from django.db.models import Sum
        member = GroupMember.objects.get(id=session.member_id)
        savings = Saving.objects.filter(member=member)
        total_deposits = savings.filter(transaction_type='deposit').aggregate(total=Sum('amount'))['total'] or 0
        total_withdrawals = savings.filter(transaction_type='withdrawal').aggregate(total=Sum('amount'))['total'] or 0
        balance = total_deposits - total_withdrawals
        return f"""END {self.get_text(session, 'savings_balance')}:
{self.get_text(session, 'total_deposits')} MK{total_deposits:,.2f}
{self.get_text(session, 'total_withdrawals')} MK{total_withdrawals:,.2f}
{self.get_text(session, 'total_balance')} MK{balance:,.2f}
{self.get_text(session, 'thank_you')}"""

    def handle_exit(self, session=None):
        thank_you = self.get_text(session, 'thank_you') if session else 'Thank you'
        return f"END {thank_you}"

    def handle_invalid(self, session):
        return f"END {self.get_text(session, 'invalid_option')}"

    # ------------------------------------------------------------------
    # Loan flow — terms fetched directly from apps.loans.models.LoanSettings
    # ------------------------------------------------------------------

    def process_loan_amount(self, session, group_code, amount):
        try:
            group = Group.objects.get(group_code=group_code)
        except Group.DoesNotExist:
            log_safe("Group missing during loan amount entry", level='warning', group_code=group_code)
            return self.handle_invalid(session)

        loan_type = session.loan_type or 'group_loan'

        try:
            min_amount, max_amount, interest_rate, duration_months = loan_module.get_loan_terms(group, loan_type)
        except LoanSettingsNotConfigured as exc:
            return f"END {exc}"

        if not (min_amount <= amount <= max_amount):
            return self.get_invalid_amount_prompt(session, group_code)

        total_payable = loan_module.calculate_total_payable(amount, interest_rate)
        session.data['interest_rate'] = str(interest_rate)
        session.data['duration_months'] = duration_months
        session.data['total_payable'] = str(total_payable)
        session.loan_amount = amount
        session.current_menu = 'otp_verification'
        session.save()

        try:
            member = GroupMember.objects.get(id=session.member_id)
        except GroupMember.DoesNotExist:
            log_safe("Member missing during loan OTP issue", level='error', member_id=session.member_id)
            return self.handle_invalid(session)

        otp_code, correlation_id = loan_module.issue_loan_otp(
            phone_number=session.phone_number,
            member_id=session.member_id,
            amount=amount,
            loan_type=loan_type,
        )
        self._send_otp_sms(member, otp_code)

        return f"""CON Loan Summary:
Amount: MK{self.format_amount(amount)}
Interest Rate: {session.data['interest_rate']}%
Total Payable: MK{self.format_amount(total_payable)}

{self.get_text(session, 'enter_otp')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

    def _send_otp_sms(self, member, otp_code):
        try:
            from apps.notifications.services import NotificationService
            notification = NotificationService()
            recipients = [r for r in (member.user, getattr(member.group, 'secretary', None)) if r]
            for recipient in recipients:
                notification.send_sms_notification(recipient, f'ECORET: Your loan OTP is: {otp_code}')
        except Exception:
            logger.exception("Failed to send loan OTP SMS to member %s", member.id)

    def handle_otp_verification(self, session, group_code, otp_code):
        record = loan_module.verify_loan_otp(phone_number=session.phone_number, otp_code=otp_code)
        if not record:
            return f"""CON {self.get_text(session, 'otp_invalid')}
{self.get_text(session, 'enter_otp')}
0. {self.get_text(session, 'back')}
00. {self._main_menu_label(session)}"""

        loan_request = loan_module.get_pending_loan_request(
            member_id=session.member_id, correlation_id=record.correlation_id
        )
        if not loan_request:
            return self.handle_invalid(session)

        loan_request.status = 'pending_approval'
        loan_request.save()

        try:
            member = GroupMember.objects.get(id=session.member_id)
            chairman = member.group.chairman
            if chairman:
                from apps.notifications.services import NotificationService
                NotificationService().send_notification(
                    chairman,
                    f'New {loan_request.loan_type} Loan Request',
                    f'{member.full_name} requested a loan of MK{loan_request.amount} via USSD.',
                    'loan_request',
                    {'loan_id': str(loan_request.id)},
                )
        except Exception:
            logger.exception("Failed to notify chairman of loan request %s", loan_request.id)

        session.current_menu = 'main'
        session.loan_amount = None
        session.loan_type = None
        session.save()

        return f"""END Loan request submitted!
Amount: MK{loan_request.amount:,.2f}
Interest Rate: {session.data.get('interest_rate', 'N/A')}%
Total Payable: MK{self.format_amount(session.data.get('total_payable', 0))}
You will be notified once approved.
{self.get_text(session, 'thank_you')}"""

    # ------------------------------------------------------------------
    # Deposits — thin wrappers around payment_service
    # ------------------------------------------------------------------

    def handle_repayment_amount(self, session, group_code, amount):
        try:
            member = GroupMember.objects.get(id=session.member_id)
        except GroupMember.DoesNotExist:
            return self.handle_invalid(session)

        loan = Loan.objects.filter(member=member, status='active').first()
        if not loan:
            return f"END {self.get_text(session, 'no_active_loans')}"

        return self._start_payment(session, member, amount, 'repayment', {'loan_id': str(loan.id)})

    def handle_savings_amount(self, session, group_code, amount):
        try:
            member = GroupMember.objects.get(id=session.member_id)
        except GroupMember.DoesNotExist:
            return self.handle_invalid(session)
        return self._start_payment(session, member, amount, 'savings', {'group_id': str(session.group_id)})

    def select_case_for_payment(self, session, group_code, case_index):
        case_id = session.data.get(f'case_{case_index}_id')
        if not case_id:
            return self.handle_invalid(session)

        try:
            case = AttendanceCase.objects.get(id=case_id, status='pending')
            member = GroupMember.objects.get(id=session.member_id)
        except (AttendanceCase.DoesNotExist, GroupMember.DoesNotExist):
            return "END This case has already been paid or does not exist."

        balance = case.penalty_amount - case.penalty_paid
        return self._start_payment(session, member, balance, 'case_penalty', {'case_id': str(case.id)})

    def _start_payment(self, session, member, amount, payment_type, payload):
        try:
            result = payment_service.start_stk_push(member=member, amount=amount, payment_type=payment_type, payload=payload)
        except PaymentError:
            return "END Payment could not be started. Please try again later."

        session.current_menu = 'payment_pending'
        session.data['payment_type'] = payment_type
        session.data['payment_amount'] = str(amount)
        session.data['payment_reference'] = result['reference']
        session.data['payment_payload'] = result['payload']
        session.save()
        return self.get_payment_pending_prompt(session)

    def complete_pending_mobile_payment(self, session):
        payment_type = session.data.get('payment_type')
        reference = session.data.get('payment_reference')
        payload = session.data.get('payment_payload', {})

        try:
            amount = int(session.data.get('payment_amount', 0))
            member = GroupMember.objects.get(id=session.member_id)
        except (ValueError, GroupMember.DoesNotExist):
            return "END Payment could not be completed. Please try again later."

        handlers = {
            'repayment': self._complete_repayment,
            'savings': self._complete_savings,
            'case_penalty': self._complete_case_penalty,
        }
        handler = handlers.get(payment_type)
        if not handler:
            return self.handle_invalid(session)

        try:
            message = handler(member, amount, reference, payload)
        except Exception:
            logger.exception("Payment completion failed for reference %s", reference)
            return "END Payment could not be completed. Please try again later."

        payment_service.mark_transaction_success(member=member, reference=reference)
        session.current_menu = 'main'
        session.save()
        return f"END {message}"

    def _complete_repayment(self, member, amount, reference, payload):
        loan = Loan.objects.get(id=payload.get('loan_id'))
        LoanRepayment.objects.create(
            loan=loan, member=member, amount=amount, principal_paid=amount,
            interest_paid=0, payment_method='mobile_money', transaction_reference=reference,
        )
        payment_service.record_audit(member=member, transaction_type='loan_repayment', amount=amount, reference=reference)
        return "Payment completed successfully. Your repayment has been recorded."

    def _complete_savings(self, member, amount, reference, payload):
        Saving.objects.create(
            group=member.group, member=member, amount=amount, saving_type='voluntary',
            transaction_type='deposit', reference_number=reference,
            notes='USSD Mobile Money Deposit',
        )
        payment_service.record_audit(member=member, transaction_type='savings_deposit', amount=amount, reference=reference)
        return "Payment completed successfully. Your savings deposit has been recorded."

    def _complete_case_penalty(self, member, amount, reference, payload):
        case_id = payload.get('case_id')
        case = AttendanceCase.objects.get(id=case_id)
        case.penalty_paid += Decimal(str(amount))
        if case.penalty_paid >= case.penalty_amount:
            case.status = 'resolved'
            case.resolved_by = member.user
            case.resolved_at = timezone.now()
        case.save()

        PenaltyPayment.objects.create(
            attendance_case=case, member=member, amount=Decimal(str(amount)),
            payment_method='mobile_money', transaction_reference=reference,
            recorded_by=member.user,
        )
        payment_service.record_audit(
            member=member, transaction_type='case_penalty_payment', amount=amount,
            reference=reference, details={'case_id': str(case_id), 'payment_reference': reference},
        )
        return "Payment completed successfully. Your case penalty has been paid."