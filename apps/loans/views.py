from rest_framework import viewsets, status, permissions, filters, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import logging

from .models import (
    Loan, LoanRepayment, LoanRequest, LoanSettings, 
    ECORETSettings, ECORETBankAccount
)
from .serializers import (
    LoanSerializer, LoanCreateSerializer, LoanUpdateSerializer,
    LoanRepaymentSerializer, LoanRepaymentCreateSerializer,
    LoanRequestSerializer, LoanRequestCreateSerializer,
    LoanSettingsSerializer, ECORETBankAccountSerializer,
    LoanDisbursementSerializer, ChairmanDisbursementSerializer,
    ECORETSettingsSerializer
)
from apps.accounts.models import UserActivityLog
from apps.notifications.services import NotificationService
from apps.groups.models import Group, GroupMember

logger = logging.getLogger(__name__)


class LoanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loans"""
    serializer_class = LoanSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'loan_type', 'group']
    search_fields = ['member__full_name', 'purpose']
    ordering_fields = ['created_at', 'due_date', 'amount']

    def get_queryset(self):
        """Override to filter based on user role - FIXED"""
        if getattr(self, 'swagger_fake_view', False):
            return Loan.objects.none()

        user = self.request.user
        
        if user.role == 'admin':
            return Loan.objects.filter(loan_type='ecoret_loan')
        
        if user.role == 'chairman':
            chairman_groups = Group.objects.filter(chairman=user).values_list('id', flat=True)
            
            secretary_groups = GroupMember.objects.filter(
                user=user,
                is_active=True
            ).values_list('group_id', flat=True)
            
            all_group_ids = list(chairman_groups) + list(secretary_groups)
            
            return Loan.objects.filter(group_id__in=all_group_ids)
        
        try:
            member = GroupMember.objects.get(user=user, is_active=True)
            return Loan.objects.filter(member=member)
        except GroupMember.DoesNotExist:
            return Loan.objects.none()

    def create(self, request):
        """Create a new loan with unified interest rate and loan limits"""
        serializer = LoanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        member = serializer.validated_data['member']
        group = member.group
        loan_type = serializer.validated_data.get('loan_type', 'group_loan')
        amount = serializer.validated_data['amount']

        if not member.is_active:
            return Response(
                {'error': 'Member is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not group.is_active:
            return Response(
                {'error': 'Group must be active to request loans'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if loan_type == 'group_loan':
            existing_loan = Loan.objects.filter(
                member=member,
                loan_type='group_loan',
                status__in=['active', 'approved']
            ).exists()
            if existing_loan:
                return Response(
                    {'error': 'Member already has an active or approved personal loan. Please complete the current loan first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if loan_type == 'ecoret_loan':
            existing_loan = Loan.objects.filter(
                group=group,
                loan_type='ecoret_loan',
                status__in=['active', 'approved']
            ).exists()
            if existing_loan:
                return Response(
                    {'error': 'Group already has an active or approved ECORET loan. Please complete the current loan first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            loan_settings = LoanSettings.objects.get(group=group)
            interest_rate = loan_settings.default_interest_rate

            if loan_type == 'group_loan':
                duration_months = loan_settings.group_loan_duration_months
                max_amount = loan_settings.group_loan_max_amount
                min_amount = loan_settings.group_loan_min_amount
            else: 
                duration_months = loan_settings.ecoret_loan_duration_months
                max_amount = loan_settings.ecoret_loan_max_amount
                min_amount = loan_settings.ecoret_loan_min_amount

        except LoanSettings.DoesNotExist:
            return Response(
                {'error': 'Loan settings not configured for this group. Please ask the chairman to set up loan settings.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount < min_amount:
            return Response(
                {'error': f'Minimum loan amount is MK{min_amount:,.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount > max_amount:
            return Response(
                {'error': f'Maximum loan amount is MK{max_amount:,.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_payable = amount * (1 + interest_rate / 100)

        loan = Loan.objects.create(
            group=group,
            member=member,
            created_by=request.user,
            loan_type=loan_type,
            amount=amount,
            interest_rate=interest_rate,
            duration_months=duration_months,
            total_payable=total_payable,
            due_date=timezone.now() + timezone.timedelta(days=duration_months * 30),
            purpose=serializer.validated_data.get('purpose', ''),
            status='pending'
        )

        UserActivityLog.objects.create(
            user=request.user,
            action='create_loan',
            details={
                'loan_id': str(loan.id),
                'amount': str(loan.amount),
                'interest_rate': str(interest_rate),
                'duration_months': duration_months
            }
        )

        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        loan = self.get_object()
    
        if loan.status != 'pending':
            return Response(
                {'error': f'Loan is not pending. Current status: {loan.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
        if request.user != loan.group.chairman:
            return Response(
                {'error': 'Only the group chairman can approve loans'},
                status=status.HTTP_403_FORBIDDEN
            )
    
        loan.status = 'approved'
        loan.approved_by = request.user
        loan.approval_date = timezone.now()
        loan.save()
    
        return Response({
            'message': 'Loan approved successfully',
            'loan': LoanSerializer(loan).data
        })

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        loan = self.get_object()
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan.status = 'declined'
        loan.save()

        return Response({'message': 'Loan declined successfully'})

    @action(detail=True, methods=['get'])
    def available_accounts(self, request, pk=None):
        loan = self.get_object()
        
        if loan.loan_type != 'ecoret_loan':
            return Response(
                {'error': 'Only ECORET loans can be disbursed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        settings = ECORETSettings.objects.first()
        if not settings:
            return Response(
                {'error': 'ECORET settings not configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        accounts = ECORETBankAccount.objects.filter(status='active')
        
        group = loan.group
        group_bank_details = {
            'group_name': group.group_name,
            'bank_name': group.bank_name or 'Not set',
            'bank_account_name': group.bank_account_name or 'Not set',
            'bank_account_number': group.bank_account_number or 'Not set',
            'bank_branch': group.bank_branch or 'Not set',
            'has_bank_details': bool(group.bank_account_number),
        }
        
        return Response({
            'accounts': ECORETBankAccountSerializer(accounts, many=True).data,
            'default_account': ECORETBankAccountSerializer(
                accounts.filter(is_default=True).first()
            ).data if accounts.filter(is_default=True).exists() else None,
            'group_bank_details': group_bank_details,
            'loan_amount': float(loan.amount),
            'loan_purpose': loan.purpose,
        })

    @action(detail=True, methods=['post'])
    def disburse_cash(self, request, pk=None):
        loan = self.get_object()
        user = request.user
        
        if loan.loan_type != 'ecoret_loan':
            return Response(
                {'error': 'Only ECORET loans can be disbursed by ECORET Admin'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        receipt_number = request.data.get('receipt_number')
        if not receipt_number:
            return Response(
                {'error': 'Cash receipt number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.mark_as_disbursed_by_ecoret('cash', user, reference=receipt_number)
        
        UserActivityLog.objects.create(
            user=user,
            action='ecoret_disburse_cash',
            details={
                'loan_id': str(loan.id),
                'amount': str(loan.amount),
                'receipt_number': receipt_number,
                'group': loan.group.group_name
            }
        )
        
        return Response({
            'message': 'Loan disbursed via cash successfully',
            'receipt_number': receipt_number,
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def disburse_bank_transfer(self, request, pk=None):
        from django.contrib.auth import authenticate
        from apps.security.services.paychangu import paychangu
        from apps.security.models import MobileMoneyTransaction

        loan = self.get_object()
        user = request.user

        if loan.loan_type != 'ecoret_loan':
            return Response(
                {'error': 'Only ECORET loans can be disbursed by ECORET Admin'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group = loan.group
        if not group.bank_account_number:
            return Response(
                {'error': 'This group has not set up bank details. Please ask the chairman to add bank details.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not group.paychangu_bank_uuid:
            return Response(
                {'error': "This group's bank has not been matched to a PayChangu bank ID yet. Contact support to complete setup."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LoanDisbursementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account_id = data.get('bank_account_id')
        try:
            account = ECORETBankAccount.objects.get(id=account_id, status='active')
        except ECORETBankAccount.DoesNotExist:
            return Response(
                {'error': 'Invalid bank account selected'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if account.balance < loan.amount:
            return Response(
                {'error': f'Insufficient balance in {account.name}. Available: MK{account.balance:,.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pin = data.get('pin')
        if not authenticate(username=user.email, password=pin):
            return Response(
                {'error': 'Incorrect PIN. Please try again.'},
                status=status.HTTP_403_FORBIDDEN
            )

        reference = data.get('transfer_reference') or f"ECORET-PAYOUT-{loan.id.hex[:8].upper()}"

        payout_result = paychangu.initiate_bank_payout(
            bank_uuid=group.paychangu_bank_uuid,
            account_number=group.bank_account_number,
            account_name=group.bank_account_name,
            amount=loan.amount,
            reference=reference,
        )

        if not payout_result.get('success'):
            return Response(
                {'error': f"Bank payout could not be started: {payout_result.get('error', 'Unknown error')}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        account.balance -= loan.amount
        account.save()

        MobileMoneyTransaction.objects.create(
            group=group,
            member=loan.member,
            transaction_type='payout',
            amount=loan.amount,
            phone_number='',
            provider='bank_transfer',
            reference=reference,
            status='pending',
            response_data={
                **payout_result.get('response', {}),
                '_ecoret_payout_loan_id': str(loan.id),
                '_ecoret_payout_account_id': str(account.id),
            },
        )

        loan.disbursement_status = 'processing'
        loan.disbursement_method = 'bank_transfer'
        loan.save(update_fields=['disbursement_status', 'disbursement_method'])

        UserActivityLog.objects.create(
            user=user,
            action='ecoret_disburse_bank_transfer',
            details={
                'loan_id': str(loan.id),
                'amount': str(loan.amount),
                'account': account.name,
                'account_number': account.account_number,
                'reference': reference,
                'group': group.group_name,
            }
        )

        return Response({
            'message': f'Bank payout initiated from {account.name}. Awaiting confirmation.',
            'transfer_reference': reference,
            'status': 'processing',
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def disburse_wait(self, request, pk=None):
        loan = self.get_object()
        user = request.user
        
        if loan.loan_type != 'ecoret_loan':
            return Response(
                {'error': 'Only ECORET loans can be managed by ECORET Admin'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason')
        if not reason:
            return Response(
                {'error': 'Please provide a reason for the wait'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.mark_as_wait_by_ecoret(user, reason)
        
        notification = NotificationService()
        notification.send_notification(
            user=loan.group.chairman,
            title="Loan Disbursement Delayed",
            message=f"Your loan of MK{loan.amount:,.2f} for {loan.group.group_name} is delayed. Reason: {reason}",
            notification_type='group_notification',
            data={'loan_id': str(loan.id), 'group_id': str(loan.group.id)}
        )
        
        UserActivityLog.objects.create(
            user=user,
            action='ecoret_disburse_wait',
            details={
                'loan_id': str(loan.id),
                'amount': str(loan.amount),
                'reason': reason,
                'group': loan.group.group_name
            }
        )
        
        return Response({
            'message': 'Loan marked as waiting for disbursement',
            'reason': reason,
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def member_bank_details(self, request, pk=None):
        loan = self.get_object()
        
        if loan.loan_type != 'group_loan':
            return Response(
                {'error': 'Only member personal loans require member bank details'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        member = loan.member
        
        member_bank_details = {
            'member_name': member.full_name,
            'member_phone': member.phone_number,
            'bank_name': member.bank_name or 'Not set',
            'bank_account_name': member.bank_account_name or 'Not set',
            'bank_account_number': member.bank_account_number or 'Not set',
            'mobile_money_provider': member.mobile_money_provider or 'Not set',
            'mobile_money_number': member.mobile_money_number or 'Not set',
            'has_bank_details': bool(member.bank_account_number),
            'has_mobile_money': bool(member.mobile_money_number),
        }
        
        return Response({
            'member_bank_details': member_bank_details,
            'loan_amount': float(loan.amount),
            'loan_purpose': loan.purpose,
            'group': {
                'id': str(loan.group.id),
                'name': loan.group.group_name,
            }
        })

    @action(detail=True, methods=['post'])
    def chairman_disburse_cash(self, request, pk=None):
        loan = self.get_object()
        user = request.user
        
        if loan.loan_type != 'group_loan':
            return Response(
                {'error': 'Only member personal loans can be disbursed by chairman'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group = loan.group
        if user.role != 'admin' and user != group.chairman:
            return Response(
                {'error': 'Only the group chairman can disburse member loans'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        receipt_number = request.data.get('receipt_number')
        if not receipt_number:
            return Response(
                {'error': 'Cash receipt number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.mark_as_disbursed_by_chairman(
            'cash', 
            user, 
            reference=receipt_number
        )
        
        UserActivityLog.objects.create(
            user=user,
            action='chairman_disburse_cash',
            details={
                'loan_id': str(loan.id),
                'member': loan.member.full_name,
                'amount': str(loan.amount),
                'receipt_number': receipt_number,
                'group': group.group_name
            }
        )
        
        return Response({
            'message': f'Cash disbursed to {loan.member.full_name} successfully',
            'receipt_number': receipt_number,
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def chairman_disburse_bank(self, request, pk=None):
        loan = self.get_object()
        user = request.user
        
        if loan.loan_type != 'group_loan':
            return Response(
                {'error': 'Only member personal loans can be disbursed by chairman'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group = loan.group
        if user.role != 'admin' and user != group.chairman:
            return Response(
                {'error': 'Only the group chairman can disburse member loans'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        member = loan.member
        if not member.bank_account_number:
            return Response(
                {'error': 'Member has not set up bank details. Please ask them to provide bank details.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transfer_reference = request.data.get('transfer_reference')
        if not transfer_reference:
            return Response(
                {'error': 'Transfer reference is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.mark_as_disbursed_by_chairman(
            'bank_transfer', 
            user, 
            reference=transfer_reference
        )
        
        UserActivityLog.objects.create(
            user=user,
            action='chairman_disburse_bank',
            details={
                'loan_id': str(loan.id),
                'member': member.full_name,
                'amount': str(loan.amount),
                'reference': transfer_reference,
                'group': group.group_name
            }
        )
        
        return Response({
            'message': f'Bank transfer to {member.full_name} completed',
            'reference': transfer_reference,
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def chairman_disburse_mobile_money(self, request, pk=None):
        loan = self.get_object()
        user = request.user
        
        if loan.loan_type != 'group_loan':
            return Response(
                {'error': 'Only member personal loans can be disbursed by chairman'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group = loan.group
        if user.role != 'admin' and user != group.chairman:
            return Response(
                {'error': 'Only the group chairman can disburse member loans'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        member = loan.member
        if not member.mobile_money_number:
            return Response(
                {'error': 'Member has not set up mobile money. Please ask them to provide mobile money details.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transaction_id = request.data.get('transaction_id')
        if not transaction_id:
            return Response(
                {'error': 'Mobile money transaction ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        provider = request.data.get('mobile_money_provider', member.mobile_money_provider)
        
        loan.mark_as_disbursed_by_chairman(
            'mobile_money', 
            user, 
            reference=transaction_id,
            provider=provider
        )
        
        UserActivityLog.objects.create(
            user=user,
            action='chairman_disburse_mobile_money',
            details={
                'loan_id': str(loan.id),
                'member': member.full_name,
                'amount': str(loan.amount),
                'transaction_id': transaction_id,
                'provider': provider,
                'group': group.group_name
            }
        )
        
        return Response({
            'message': f'Mobile money sent to {member.full_name} successfully',
            'transaction_id': transaction_id,
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def chairman_disburse_wait(self, request, pk=None):
        loan = self.get_object()
        user = request.user
        
        if loan.loan_type != 'group_loan':
            return Response(
                {'error': 'Only member personal loans can be managed by chairman'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group = loan.group
        if user.role != 'admin' and user != group.chairman:
            return Response(
                {'error': 'Only the group chairman can manage member loans'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reason = request.data.get('reason')
        if not reason:
            return Response(
                {'error': 'Please provide a reason for the wait'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan.mark_as_wait_by_chairman(user, reason)
        
        if loan.member.user:
            notification = NotificationService()
            notification.send_notification(
                user=loan.member.user,
                title="Loan Disbursement Delayed",
                message=f"Your loan of MK{loan.amount:,.2f} is delayed. Reason: {reason}",
                notification_type='group_notification',
                data={'loan_id': str(loan.id)}
            )
        
        UserActivityLog.objects.create(
            user=user,
            action='chairman_disburse_wait',
            details={
                'loan_id': str(loan.id),
                'member': loan.member.full_name,
                'amount': str(loan.amount),
                'reason': reason,
                'group': group.group_name
            }
        )
        
        return Response({
            'message': 'Loan marked as waiting for disbursement',
            'reason': reason,
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def record_repayment(self, request, pk=None):
        """Record a loan repayment"""
        try:
            loan = self.get_object()
        except Loan.DoesNotExist:
            return Response(
                {'error': 'Loan not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        logger.info(f"Recording repayment for loan {loan.id}")
        logger.info(f"Loan status: {loan.status}")
        logger.info(f"Loan balance: {loan.get_balance()}")
        logger.info(f"Request data: {request.data}")
        
        if loan.status not in ['active', 'approved']:
            return Response(
                {'error': f'Cannot make repayment on this loan. Current status: {loan.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = request.data.get('amount')
        if amount is None:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from decimal import Decimal
            amount = Decimal(str(amount))
        except Exception as e:
            return Response(
                {'error': f'Invalid amount format: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount <= 0:
            return Response(
                {'error': 'Amount must be greater than zero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        balance = loan.get_balance()
        if amount > balance:
            return Response(
                {'error': f'Amount exceeds balance. Balance: {balance}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.db.models import Sum
        total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0
        remaining_principal = loan.total_payable - total_paid
        
        if amount <= remaining_principal:
            principal_paid = amount
            interest_paid = 0
        else:
            principal_paid = remaining_principal
            interest_paid = amount - remaining_principal
        
        payment_method = request.data.get('payment_method', 'cash')
        transaction_reference = request.data.get('transaction_reference', '')
        notes = request.data.get('notes', '')
        
        repayment = LoanRepayment.objects.create(
            loan=loan,
            member=loan.member,
            recorded_by=request.user,
            amount=amount,
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            notes=notes,
            payment_date=timezone.now()
        )
        
        logger.info(f"Repayment created: {repayment.id}")
        logger.info(f"Amount: {amount}, Principal: {principal_paid}, Interest: {interest_paid}")
        
        new_balance = loan.get_balance()
        if new_balance <= 0:
            loan.status = 'completed'
            loan.save()
            logger.info(f"Loan {loan.id} automatically marked as completed")
        
        UserActivityLog.objects.create(
            user=request.user,
            action='record_repayment',
            details={
                'loan_id': str(loan.id),
                'amount': str(repayment.amount),
                'payment_method': repayment.payment_method,
                'transaction_reference': repayment.transaction_reference,
                'remaining_balance': str(new_balance)
            }
        )
        
        response_data = {
            'id': str(repayment.id),
            'loan': str(loan.id),
            'member': str(loan.member.id),
            'member_name': loan.member.full_name,
            'amount': float(repayment.amount),
            'principal_paid': float(repayment.principal_paid),
            'interest_paid': float(repayment.interest_paid),
            'payment_method': repayment.payment_method,
            'transaction_reference': repayment.transaction_reference,
            'notes': repayment.notes,
            'payment_date': repayment.payment_date.isoformat(),
            'recorded_at': repayment.recorded_at.isoformat(),
            'remaining_balance': float(new_balance),
            'loan_status': loan.status,
            'is_completed': loan.status == 'completed'
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        loan = self.get_object()
        balance = loan.get_balance()
        total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0

        return Response({
            'total_payable': loan.total_payable,
            'total_paid': total_paid,
            'balance': balance,
            'is_completed': balance <= 0
        })

    @action(detail=True, methods=['get'])
    def repayments(self, request, pk=None):
        loan = self.get_object()
        repayments = loan.repayments.all()
        serializer = LoanRepaymentSerializer(repayments, many=True)
        return Response(serializer.data)


class LoanRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LoanRequestSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'group']
    search_fields = ['group__group_name', 'purpose']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return LoanRequest.objects.none()

        user = self.request.user

        if user.role == 'admin':
            return LoanRequest.objects.all()

        if user.role == 'chairman':
            chairman_groups = Group.objects.filter(chairman=user).values_list('id', flat=True)
            return LoanRequest.objects.filter(group_id__in=chairman_groups)

        return LoanRequest.objects.none()

    def create(self, request):
        groups = request.user.chairman_groups.all()
        if not groups.exists():
            return Response(
                {'error': 'You must be a group chairman to request a loan'},
                status=status.HTTP_403_FORBIDDEN
            )

        group = groups.first()

        serializer = LoanRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        loan_request = LoanRequest.objects.create(
            group=group,
            requested_by=request.user,
            **serializer.validated_data
        )

        notification = NotificationService()
        notification.send_new_loan_request_notification(loan_request)

        UserActivityLog.objects.create(
            user=request.user,
            action='request_loan',
            details={'request_id': str(loan_request.id)}
        )

        return Response(LoanRequestSerializer(loan_request).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET admin can approve loan requests'},
                status=status.HTTP_403_FORBIDDEN
            )

        loan_request = self.get_object()
        if loan_request.status != 'pending':
            return Response(
                {'error': 'Request is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        approved_amount_raw = request.data.get('approved_amount', loan_request.amount)
        try:
            amount = Decimal(str(approved_amount_raw))
        except Exception:
            return Response(
                {'error': 'Invalid approved_amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount <= 0:
            return Response(
                {'error': 'Approved amount must be greater than 0'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount > loan_request.amount:
            return Response(
                {'error': 'Approved amount cannot exceed the requested amount'},
                status=status.HTTP_400_BAD_REQUEST
            )

        chairman = loan_request.group.chairman
        if not chairman:
            return Response(
                {'error': 'Group has no chairman'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member = loan_request.group.members.filter(user=chairman).first()
        if not member:
            return Response(
                {'error': 'Chairman not found in group members'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_ecoret_loan = Loan.objects.filter(
            group=loan_request.group,
            loan_type='ecoret_loan',
            status__in=['active', 'approved']
        ).exists()
        if existing_ecoret_loan:
            return Response(
                {'error': 'This group already has an active or approved ECORET loan. Please complete the current loan before approving another request.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ecoret_settings = ECORETSettings.objects.first()
        if not ecoret_settings:
            return Response(
                {'error': 'ECORET settings not configured. Contact admin.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        interest_rate = ecoret_settings.ecoret_loan_interest_rate
        duration_months = ecoret_settings.ecoret_loan_duration_months
        max_amount = ecoret_settings.ecoret_loan_max_amount
        min_amount = ecoret_settings.ecoret_loan_min_amount

        if amount < min_amount:
            return Response(
                {'error': f'ECORET minimum loan is MK{min_amount:,.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount > max_amount:
            return Response(
                {'error': f'ECORET maximum loan is MK{max_amount:,.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan = Loan.objects.create(
            group=loan_request.group,
            member=member,
            loan_type='ecoret_loan',
            amount=amount,
            interest_rate=interest_rate,
            total_payable=amount * (1 + interest_rate / 100),
            duration_months=duration_months,
            purpose=loan_request.purpose,
            status='approved',
            approved_by=request.user,
            due_date=timezone.now() + timezone.timedelta(days=duration_months * 30)
        )

        loan_request.approved_amount = amount
        loan_request.approve(request.user)

        notification = NotificationService()
        notification.send_loan_request_approved_notification(loan_request)

        UserActivityLog.objects.create(
            user=request.user,
            action='approve_ecoret_loan',
            details={
                'request_id': str(loan_request.id),
                'loan_id': str(loan.id),
                'requested_amount': str(loan_request.amount),
                'approved_amount': str(amount),
                'interest_rate': str(interest_rate),
                'duration_months': duration_months
            }
        )

        return Response({
            'message': 'Loan request approved. Loan is now ready for disbursement.',
            'loan': LoanSerializer(loan).data
        })

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET admin can decline loan requests'},
                status=status.HTTP_403_FORBIDDEN
            )

        loan_request = self.get_object()
        if loan_request.status != 'pending':
            return Response(
                {'error': 'Request is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan_request.decline(request.user)

        return Response({'message': 'Loan request declined'})


class LoanSettingsViewSet(viewsets.ModelViewSet):
    serializer_class = LoanSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return LoanSettings.objects.none()

        user = self.request.user
        
        if user.role == 'admin':
            return LoanSettings.objects.all()
        
        if user.role == 'chairman':
            chairman_groups = Group.objects.filter(chairman=user).values_list('id', flat=True)
            return LoanSettings.objects.filter(group_id__in=chairman_groups)
        
        return LoanSettings.objects.none()

    def create(self, request):
        group = request.user.chairman_groups.first()
        if not group:
            return Response(
                {'error': 'You must be a chairman to set loan settings'},
                status=status.HTTP_403_FORBIDDEN
            )

        if LoanSettings.objects.filter(group=group).exists():
            return Response(
                {'error': 'Loan settings already exist for this group'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LoanSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data.copy()
        validated_data.pop('group', None)

        settings = LoanSettings.objects.create(
            group=group,
            **validated_data
        )

        return Response(LoanSettingsSerializer(settings).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'])
    def update_settings(self, request, pk=None):
        settings = self.get_object()
        serializer = LoanSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        UserActivityLog.objects.create(
            user=request.user,
            action='update_loan_settings',
            details={'group_id': str(settings.group.id)}
        )

        return Response(serializer.data)


class ECORETSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ECORET global settings
    Only ECORET Admin can access this
    """
    queryset = ECORETSettings.objects.all()
    serializer_class = ECORETSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return ECORETSettings.objects.all()
        return ECORETSettings.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class ECORETBankAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ECORET bank accounts
    Admin can manage all, Chairman can only view active accounts
    """
    queryset = ECORETBankAccount.objects.all()
    serializer_class = ECORETBankAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return ECORETBankAccount.objects.all()
        elif user.role == 'chairman':
            return ECORETBankAccount.objects.filter(status='active')
        return ECORETBankAccount.objects.none()
    
    def perform_create(self, serializer):
        account = serializer.save(
            status='pending_verification'
        )
        UserActivityLog.objects.create(
            user=self.request.user,
            action='create_bank_account',
            details={
                'account_id': str(account.id),
                'account_name': account.name,
                'bank_name': account.bank_name,
                'account_number': account.account_number
            }
        )
    
    def perform_update(self, serializer):
        account = serializer.save()
        UserActivityLog.objects.create(
            user=self.request.user,
            action='update_bank_account',
            details={
                'account_id': str(account.id),
                'account_name': account.name
            }
        )
    
    def perform_destroy(self, instance):
        if instance.is_default:
            raise serializers.ValidationError(
                {'error': 'Cannot delete the default account. Set another account as default first.'}
            )
        UserActivityLog.objects.create(
            user=self.request.user,
            action='delete_bank_account',
            details={
                'account_id': str(instance.id),
                'account_name': instance.name
            }
        )
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        account = self.get_object()
        
        ECORETBankAccount.objects.filter(is_default=True).update(is_default=False)
        
        account.is_default = True
        account.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action='set_default_bank_account',
            details={
                'account_id': str(account.id),
                'account_name': account.name
            }
        )
        
        return Response({
            'message': f'{account.name} set as default account successfully',
            'account': ECORETBankAccountSerializer(account).data
        })
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        account = self.get_object()
        
        if account.status == 'active':
            return Response(
                {'error': 'Account is already verified and active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if account.status == 'pending_verification':
            account.status = 'active'
            account.save()
            
            UserActivityLog.objects.create(
                user=request.user,
                action='verify_bank_account',
                details={
                    'account_id': str(account.id),
                    'account_name': account.name,
                    'bank_name': account.bank_name,
                    'account_number': account.account_number
                }
            )
            
            return Response({
                'message': f'{account.name} has been verified and activated successfully',
                'account': ECORETBankAccountSerializer(account).data
            })
        else:
            return Response(
                {'error': f'Cannot verify account with status: {account.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        account = self.get_object()
        
        if account.status == 'inactive':
            return Response(
                {'error': 'Account is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if account.is_default:
            return Response(
                {'error': 'Cannot deactivate the default account. Set another account as default first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        account.status = 'inactive'
        account.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action='deactivate_bank_account',
            details={
                'account_id': str(account.id),
                'account_name': account.name,
                'bank_name': account.bank_name,
                'account_number': account.account_number
            }
        )
        
        return Response({
            'message': f'{account.name} has been deactivated',
            'account': ECORETBankAccountSerializer(account).data
        })
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        account = self.get_object()
        
        if account.status == 'active':
            return Response(
                {'error': 'Account is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        account.status = 'active'
        account.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action='reactivate_bank_account',
            details={
                'account_id': str(account.id),
                'account_name': account.name,
                'bank_name': account.bank_name,
                'account_number': account.account_number
            }
        )
        
        return Response({
            'message': f'{account.name} has been reactivated',
            'account': ECORETBankAccountSerializer(account).data
        })