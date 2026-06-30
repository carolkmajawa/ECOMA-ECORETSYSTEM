from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.db.models import Sum
from apps.groups.models import Group, GroupMember
from apps.loans.models import Loan, LoanRepayment
from apps.savings.models import Saving
from .models import USSDSession, USSDOTP, USSDLoanRequest
from .languages import LanguageTranslations
import uuid
import logging
import re

logger = logging.getLogger(__name__)

class USSDView(APIView):
    """Main USSD handler with fixed amount input and multi-language support"""
    permission_classes = [AllowAny]
    
    def __init__(self):
        self.translations = LanguageTranslations()
    
    def get_text(self, session, key, **kwargs):
        """Get translated text for current language"""
        language = getattr(session, 'language', 'en')
        return self.translations.get_text(language, key, **kwargs)
    
    def post(self, request):
        data = request.data
        phone_number = data.get('phoneNumber')
        session_id = data.get('sessionId')
        service_code = data.get('serviceCode')
        text = data.get('text', '')
        
        logger.info(f"USSD Request - Phone: {phone_number}, Text: {text}")
        
        # Get or create session
        session = self.get_or_create_session(session_id, phone_number)
        
        # Process based on text
        if text == '':
            response = self.handle_welcome(session)
        else:
            response = self.handle_menu(session, text)
        
        return Response(response, content_type='text/plain')
    
    def get_or_create_session(self, session_id, phone_number):
        """Get or create USSD session"""
        session, created = USSDSession.objects.get_or_create(
            session_id=session_id,
            defaults={
                'phone_number': phone_number,
                'current_menu': 'welcome',
                'language': 'en'
            }
        )
        if not created:
            session.phone_number = phone_number
            session.save()
        return session
    
    def reset_session_to_main(self, session):
        """Reset session state to main menu"""
        session.current_menu = 'main'
        session.loan_type = None
        session.loan_amount = None
        session.data = {}
        session.save()
        if session.group_code:
            return self.get_main_menu(session, session.group_code)
        return self.handle_welcome(session)
    
    def handle_welcome(self, session):
        """Handle welcome screen"""
        session.current_menu = 'language'
        session.save()
        
        welcome = self.get_text(session, 'welcome')
        choose_lang = self.get_text(session, 'choose_language')
        exit = self.get_text(session, 'exit')
        
        return f"""CON {welcome}
1. English
2. Chichewa
0. {exit}"""
    
    def handle_menu(self, session, text):
        """Handle menu navigation with fixed amount input"""
        parts = text.split('*')
        level = len(parts)
        
        # Check for "00" - Go to Main Menu
        if text.endswith('00'):
            if session.group_code and session.member_id:
                return self.reset_session_to_main(session)
            else:
                return self.handle_welcome(session)
        
        # Check for "0" - Go Back One Step (only if it's a single 0, not part of a number)
        if text.endswith('0') and not text.endswith('00'):
            # Make sure it's not part of an amount (like 1000)
            # Check if the last character is 0 and the second last is not 0
            if len(text) == 1 or (len(text) > 1 and text[-2] != '*'):
                # But if the user is entering an amount with 0 at the end (like 1000), we don't want to go back
                # Check if this is a level where amount is expected
                if level == 5 and parts[4].endswith('0'):
                    # This is an amount ending with 0, don't go back
                    pass
                else:
                    return self.handle_back(session, level)
        
        # Language selection - LEVEL 1
        if level == 1:
            if parts[0] == '1':
                session.language = 'en'
                session.current_menu = 'group_code'
                session.data = {}
                session.save()
                logger.info(f"Language set to English for session {session.session_id}")
                return self.get_group_code_prompt(session)
            elif parts[0] == '2':
                session.language = 'ny'
                session.current_menu = 'group_code'
                session.group_code = None
                session.member_id = None
                session.group_id = None
                session.loan_type = None
                session.loan_amount = None
                session.data = {}
                session.save()
                logger.info(f"Language set to Chichewa for session {session.session_id}")
                return self.get_group_code_prompt(session)
            elif parts[0] == '0':
                return self.handle_exit(session)
            else:
                return self.handle_invalid(session)
        
        # Group code input - LEVEL 2
        elif level == 2:
            if parts[0] == '1' and parts[1].isdigit():
                group_code = parts[1]
                return self.handle_group_code(session, group_code)
            elif parts[1] == '0':
                return self.handle_welcome(session)
            else:
                return self.handle_invalid(session)
        
        # Main menu - LEVEL 3
        elif level == 3:
            group_code = parts[1]
            choice = parts[2]
            
            if choice == '1':
                return self.get_loan_type_menu(session, group_code)
            elif choice == '2':
                session.current_menu = 'deposit_menu'
                session.save()
                return self.get_deposit_menu(session, group_code)
            elif choice == '3':
                session.current_menu = 'balance_menu'
                session.save()
                return self.get_balance_menu(session, group_code)
            elif choice == '4':
                return self.handle_my_info(session, group_code)
            elif choice == '0':
                return self.handle_exit(session)
            else:
                return self.handle_invalid(session)
        
        # Loan Type Selection - LEVEL 4
        elif level == 4:
            group_code = parts[1]
            main_choice = parts[2]
            sub_choice = parts[3]
            
            # Loan type selection
            if main_choice == '1':
                if sub_choice == '1' or sub_choice == '2':
                    session.loan_type = 'group_loan' if sub_choice == '1' else 'ecoret_loan'
                    session.current_menu = 'loan_amount'
                    session.save()
                    return self.get_loan_amount_prompt(session, group_code)
                elif sub_choice == '0':
                    return self.get_main_menu(session, group_code)
                elif sub_choice == '00':
                    return self.reset_session_to_main(session)
                else:
                    return self.handle_invalid(session)
            
            # Deposit submenu
            elif main_choice == '2':
                if sub_choice == '1':
                    session.current_menu = 'repayment_amount'
                    session.save()
                    return self.get_repayment_amount_prompt(session, group_code)
                elif sub_choice == '2':
                    session.current_menu = 'savings_amount'
                    session.save()
                    return self.get_savings_amount_prompt(session, group_code)
                elif sub_choice == '0':
                    return self.get_main_menu(session, group_code)
                elif sub_choice == '00':
                    return self.reset_session_to_main(session)
                else:
                    return self.handle_invalid(session)
            
            # Balance submenu
            elif main_choice == '3':
                if sub_choice == '1':
                    return self.handle_loan_balance(session, group_code)
                elif sub_choice == '2':
                    return self.handle_savings_balance(session, group_code)
                elif sub_choice == '0':
                    return self.get_main_menu(session, group_code)
                elif sub_choice == '00':
                    return self.reset_session_to_main(session)
                else:
                    return self.handle_invalid(session)
            
            else:
                return self.handle_invalid(session)
        
        # Amount input - LEVEL 5 (FIXED)
        elif level == 5:
            group_code = parts[1]
            main_choice = parts[2]
            sub_choice = parts[3]
            amount = parts[4]
            
            # Check if amount is "00" going to main menu
            if amount == '00':
                return self.reset_session_to_main(session)
            
            # Check if amount is "0" going back (only if it's just 0)
            if amount == '0':
                return self.handle_back(session, level)
            
            # Loan amount input (main_choice == '1')
            if main_choice == '1':
                # Check if amount is a valid number
                if amount.isdigit():
                    amount_int = int(amount)
                    if amount_int > 0:
                        return self.handle_loan_amount(session, group_code, amount)
                    else:
                        return self.get_invalid_amount_prompt(session, group_code)
                else:
                    return self.get_invalid_amount_prompt(session, group_code)
            
            # Repayment amount input (main_choice == '2', sub_choice == '1')
            elif main_choice == '2' and sub_choice == '1':
                if amount.isdigit():
                    amount_int = int(amount)
                    if amount_int > 0:
                        return self.handle_repayment_amount(session, group_code, amount)
                    else:
                        return self.get_invalid_amount_prompt(session, group_code)
                else:
                    return self.get_invalid_amount_prompt(session, group_code)
            
            # Savings amount input (main_choice == '2', sub_choice == '2')
            elif main_choice == '2' and sub_choice == '2':
                if amount.isdigit():
                    amount_int = int(amount)
                    if amount_int > 0:
                        return self.handle_savings_amount(session, group_code, amount)
                    else:
                        return self.get_invalid_amount_prompt(session, group_code)
                else:
                    return self.get_invalid_amount_prompt(session, group_code)
            
            # OTP verification (when amount is actually OTP)
            elif main_choice == '1' and sub_choice == '1' and amount.isdigit():
                return self.handle_otp_verification(session, group_code, amount)
            
            else:
                return self.get_invalid_amount_prompt(session, group_code)
        
        # Default: invalid option
        return self.handle_invalid(session)
    
    def handle_back(self, session, level):
        """Handle going back one step (0)"""
        if level == 1:
            return self.handle_welcome(session)
        elif level == 2:
            return self.handle_welcome(session)
        elif level == 3:
            if session.group_code:
                return self.get_main_menu(session, session.group_code)
            return self.handle_welcome(session)
        elif level == 4:
            if session.current_menu == 'loan_amount':
                return self.get_loan_type_menu(session, session.group_code)
            elif session.current_menu == 'deposit_menu':
                return self.get_main_menu(session, session.group_code)
            elif session.current_menu == 'balance_menu':
                return self.get_main_menu(session, session.group_code)
            else:
                return self.get_main_menu(session, session.group_code)
        elif level == 5:
            if session.current_menu == 'loan_amount':
                return self.get_loan_type_menu(session, session.group_code)
            elif session.current_menu == 'repayment_amount':
                return self.get_deposit_menu(session, session.group_code)
            elif session.current_menu == 'savings_amount':
                return self.get_deposit_menu(session, session.group_code)
            elif session.current_menu == 'otp_verification':
                return self.get_loan_amount_prompt(session, session.group_code)
            else:
                return self.get_main_menu(session, session.group_code)
        return self.get_main_menu(session, session.group_code) if session.group_code else self.handle_welcome(session)
    
    def get_group_code_prompt(self, session):
        """Get group code prompt"""
        enter_code = self.get_text(session, 'enter_group_code')
        back = self.get_text(session, 'back')
        return f"""CON {enter_code}
0. {back}"""
    
    def get_main_menu(self, session, group_code):
        """Get main menu"""
        try:
            member = GroupMember.objects.get(id=session.member_id)
            welcome = self.get_text(session, 'main_menu', name=member.full_name)
            take_loan = self.get_text(session, 'take_loan')
            deposit = self.get_text(session, 'deposit')
            check_balance = self.get_text(session, 'check_balance')
            my_info = self.get_text(session, 'my_info')
            back = self.get_text(session, 'back')
            exit = self.get_text(session, 'exit')
            
            return f"""CON {welcome}
1. {take_loan}
2. {deposit}
3. {check_balance}
4. {my_info}
0. {back}
00. {exit}"""
        except:
            return self.handle_exit(session)
    
    def get_loan_type_menu(self, session, group_code):
        """Get loan type menu"""
        take_loan = self.get_text(session, 'take_loan')
        group_loan = self.get_text(session, 'group_loan')
        ecoret_loan = self.get_text(session, 'ecoret_loan')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        
        return f"""CON {take_loan}
1. {group_loan}
2. {ecoret_loan}
0. {back}
00. {main_menu}"""
    
    def get_loan_amount_prompt(self, session, group_code):
        """Get loan amount prompt"""
        loan_amount = self.get_text(session, 'loan_amount')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        min_amount = self.get_text(session, 'min_amount', amount='1,000')
        max_amount = self.get_text(session, 'max_amount', amount='1,000,000')
        
        return f"""CON {loan_amount}
{min_amount}
{max_amount}
0. {back}
00. {main_menu}"""
    
    def get_deposit_menu(self, session, group_code):
        """Get deposit menu"""
        deposit_options = self.get_text(session, 'deposit_options')
        repay_loan = self.get_text(session, 'repay_loan')
        pay_savings = self.get_text(session, 'pay_savings')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        
        return f"""CON {deposit_options}
1. {repay_loan}
2. {pay_savings}
0. {back}
00. {main_menu}"""
    
    def get_balance_menu(self, session, group_code):
        """Get balance menu"""
        balance_options = self.get_text(session, 'balance_options')
        loan_balance = self.get_text(session, 'loan_balance')
        savings_balance = self.get_text(session, 'savings_balance')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        
        return f"""CON {balance_options}
1. {loan_balance}
2. {savings_balance}
0. {back}
00. {main_menu}"""
    
    def get_repayment_amount_prompt(self, session, group_code):
        """Get repayment amount prompt"""
        repayment_amount = self.get_text(session, 'repayment_amount')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        return f"""CON {repayment_amount}
0. {back}
00. {main_menu}"""
    
    def get_savings_amount_prompt(self, session, group_code):
        """Get savings amount prompt"""
        savings_amount = self.get_text(session, 'savings_amount')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        return f"""CON {savings_amount}
0. {back}
00. {main_menu}"""
    
    def get_invalid_amount_prompt(self, session, group_code):
        """Get invalid amount prompt"""
        invalid_amount = self.get_text(session, 'invalid_amount')
        back = self.get_text(session, 'back')
        main_menu = self.get_text(session, 'main_menu')
        return f"""CON {invalid_amount}
0. {back}
00. {main_menu}"""
    
    def handle_group_code(self, session, group_code):
        """Validate group code with language support"""
        try:
            logger.info(f"Validating group code {group_code} for phone {session.phone_number}")
            
            # Try to find the group
            try:
                group = Group.objects.get(group_code=group_code, is_active=True)
            except Group.DoesNotExist:
                invalid_group = self.get_text(session, 'invalid_group')
                return f"END {invalid_group}"
            
            # Check if member exists in this group
            member = GroupMember.objects.filter(
                group=group,
                phone_number=session.phone_number,
                is_active=True
            ).first()
            
            if member:
                # Save session data
                session.group_code = group_code
                session.group_id = group.id
                session.member_id = member.id
                session.current_menu = 'main'
                session.save()
                
                logger.info(f"Member {member.full_name} validated for group {group.group_name}")
                return self.get_main_menu(session, group_code)
            else:
                not_registered = self.get_text(session, 'not_registered')
                logger.warning(f"Phone {session.phone_number} not registered in group {group_code}")
                return f"END {not_registered}"
                
        except Exception as e:
            logger.error(f"Group code validation error: {str(e)}")
            return self.handle_invalid(session)
    
    def handle_loan_amount(self, session, group_code, amount):
        """Handle loan amount input with OTP"""
        try:
            amount = int(amount)
            
            if amount < 1000:
                return self.get_loan_amount_prompt(session, group_code)
            
            if amount > 1000000:
                return self.get_loan_amount_prompt(session, group_code)
            
            # Generate OTP
            otp = self.generate_otp()
            correlation_id = str(uuid.uuid4())
            
            # Save OTP
            USSDOTP.objects.create(
                phone_number=session.phone_number,
                otp_code=otp,
                purpose='loan_approval',
                expires_at=timezone.now() + timezone.timedelta(minutes=5),
                correlation_id=correlation_id
            )
            
            # Save loan request
            USSDLoanRequest.objects.create(
                member_id=session.member_id,
                amount=amount,
                loan_type=session.loan_type or 'group_loan',
                otp_session_id=correlation_id,
                status='pending_otp'
            )
            
            # Send OTP via SMS
            try:
                from apps.notifications.services import NotificationService
                notification = NotificationService()
                member = GroupMember.objects.get(id=session.member_id)
                if member.user:
                    notification.send_sms_notification(
                        member.user,
                        f'ECORET: Your loan OTP is: {otp}'
                    )
            except Exception as e:
                logger.error(f'Failed to send OTP SMS: {str(e)}')
            
            session.loan_amount = amount
            session.current_menu = 'otp_verification'
            session.save()
            
            enter_otp = self.get_text(session, 'enter_otp')
            back = self.get_text(session, 'back')
            main_menu = self.get_text(session, 'main_menu')
            
            return f"""CON {enter_otp}
0. {back}
00. {main_menu}"""
            
        except ValueError:
            return self.get_invalid_amount_prompt(session, group_code)
    
    def handle_otp_verification(self, session, group_code, otp_code):
        """Verify OTP and process loan"""
        try:
            # Validate OTP
            otp_record = USSDOTP.objects.filter(
                phone_number=session.phone_number,
                otp_code=otp_code,
                purpose='loan_approval',
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp_record:
                enter_otp = self.get_text(session, 'enter_otp')
                invalid = self.get_text(session, 'otp_invalid')
                back = self.get_text(session, 'back')
                main_menu = self.get_text(session, 'main_menu')
                return f"""CON {invalid}
{enter_otp}
0. {back}
00. {main_menu}"""
            
            # Get loan request
            loan_request = USSDLoanRequest.objects.filter(
                member_id=session.member_id,
                otp_session_id=otp_record.correlation_id,
                status='pending_otp'
            ).first()
            
            if not loan_request:
                return self.handle_invalid(session)
            
            # Mark OTP as used
            otp_record.is_used = True
            otp_record.save()
            
            # Update loan request
            loan_request.status = 'pending_approval'
            loan_request.save()
            
            # Send notification to chairman
            try:
                from apps.notifications.services import NotificationService
                notification = NotificationService()
                member = GroupMember.objects.get(id=session.member_id)
                chairman = member.group.chairman
                
                if chairman:
                    notification.send_notification(
                        chairman,
                        f'New {loan_request.loan_type} Loan Request',
                        f'{member.full_name} requested a loan of MK{loan_request.amount} via USSD.',
                        'loan_request',
                        {'loan_id': str(loan_request.id)}
                    )
            except Exception as e:
                logger.error(f'Failed to send chairman notification: {str(e)}')
            
            # Reset session
            session.current_menu = 'main'
            session.loan_amount = None
            session.loan_type = None
            session.save()
            
            # Send confirmation to member
            thank_you = self.get_text(session, 'thank_you')
            return f"""END Loan request submitted!
Amount: MK{loan_request.amount:,.2f}
You will be notified once approved.
{thank_you}"""
            
        except Exception as e:
            logger.error(f'OTP verification error: {str(e)}')
            return self.handle_invalid(session)
    
    def handle_repayment_amount(self, session, group_code, amount):
        """Handle repayment amount input"""
        try:
            amount = int(amount)
            member = GroupMember.objects.get(id=session.member_id)
            active_loans = Loan.objects.filter(
                member=member,
                status='active'
            )
            
            if not active_loans.exists():
                no_loans = self.get_text(session, 'no_active_loans')
                return f"END {no_loans}"
            
            # Record repayment
            loan = active_loans.first()
            LoanRepayment.objects.create(
                loan=loan,
                member=member,
                amount=amount,
                principal_paid=amount,
                interest_paid=0,
                payment_method='ussd',
                transaction_reference=f'USSD_{int(timezone.now().timestamp())}'
            )
            
            transaction_approved = self.get_text(session, 'transaction_approved')
            thank_you = self.get_text(session, 'thank_you')
            
            # Reset session
            session.current_menu = 'main'
            session.save()
            
            return f"END {transaction_approved}\n{thank_you}"
            
        except ValueError:
            return self.get_invalid_amount_prompt(session, group_code)
    
    def handle_savings_amount(self, session, group_code, amount):
        """Handle savings amount input"""
        try:
            amount = int(amount)
            
            if amount < 100:
                min_amount = self.get_text(session, 'min_amount', amount='100')
                return f"END {min_amount}"
            
            member = GroupMember.objects.get(id=session.member_id)
            
            # Record savings
            Saving.objects.create(
                group_id=session.group_id,
                member=member,
                amount=amount,
                saving_type='voluntary',
                transaction_type='deposit',
                reference_number=f'USSD_SAV_{int(timezone.now().timestamp())}',
                notes='USSD Deposit'
            )
            
            savings_deposit = self.get_text(session, 'savings_deposit')
            thank_you = self.get_text(session, 'thank_you')
            
            # Reset session
            session.current_menu = 'main'
            session.save()
            
            return f"END {savings_deposit}\n{thank_you}"
            
        except ValueError:
            return self.get_invalid_amount_prompt(session, group_code)
    
    def handle_loan_balance(self, session, group_code):
        """Display loan balance"""
        member = GroupMember.objects.get(id=session.member_id)
        loans = Loan.objects.filter(member=member, status__in=['active', 'approved'])
        
        if not loans.exists():
            no_loans = self.get_text(session, 'no_active_loans')
            return f"END {no_loans}"
        
        total_balance = 0
        loan_balance_text = self.get_text(session, 'loan_balance')
        message = f"{loan_balance_text}:\n"
        
        for loan in loans:
            balance = loan.get_balance()
            total_balance += balance
            message += f"- MK{loan.amount:,.2f}: MK{balance:,.2f}\n"
        
        total_text = self.get_text(session, 'total_balance')
        message += f"\n{total_text} MK{total_balance:,.2f}"
        
        thank_you = self.get_text(session, 'thank_you')
        return f"END {message}\n{thank_you}"
    
    def handle_savings_balance(self, session, group_code):
        """Display savings balance"""
        member = GroupMember.objects.get(id=session.member_id)
        savings = Saving.objects.filter(member=member)
        
        total_deposits = savings.filter(transaction_type='deposit').aggregate(total=Sum('amount'))['total'] or 0
        total_withdrawals = savings.filter(transaction_type='withdrawal').aggregate(total=Sum('amount'))['total'] or 0
        balance = total_deposits - total_withdrawals
        
        savings_balance_text = self.get_text(session, 'savings_balance')
        total_deposits_text = self.get_text(session, 'total_deposits')
        total_withdrawals_text = self.get_text(session, 'total_withdrawals')
        total_balance_text = self.get_text(session, 'total_balance')
        thank_you = self.get_text(session, 'thank_you')
        
        return f"""END {savings_balance_text}:
{total_deposits_text} MK{total_deposits:,.2f}
{total_withdrawals_text} MK{total_withdrawals:,.2f}
{total_balance_text} MK{balance:,.2f}
{thank_you}"""
    
    def handle_my_info(self, session, group_code):
        """Display member information"""
        member = GroupMember.objects.get(id=session.member_id)
        
        member_info = self.get_text(session, 'member_info')
        name = self.get_text(session, 'name')
        phone = self.get_text(session, 'phone')
        group = self.get_text(session, 'group')
        member_since = self.get_text(session, 'member_since')
        thank_you = self.get_text(session, 'thank_you')
        
        return f"""END {member_info}
{name}: {member.full_name}
{phone}: {member.phone_number}
{group}: {member.group.group_name}
{member_since} {member.joined_date.strftime('%Y-%m-%d')}
{thank_you}"""
    
    def generate_otp(self):
        """Generate 6-digit OTP"""
        import random
        return ''.join(random.choices('0123456789', k=6))
    
    def handle_exit(self, session=None):
        """Handle exit"""
        thank_you = self.get_text(session, 'thank_you') if session else 'Thank you'
        return f"END {thank_you}"
    
    def handle_invalid(self, session):
        """Handle invalid option"""
        invalid = self.get_text(session, 'invalid_option')
        return f"END {invalid}"