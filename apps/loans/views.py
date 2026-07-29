# from rest_framework import viewsets, status, permissions, filters
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from django.db.models import Q, Sum
# from django.shortcuts import get_object_or_404
# from django.utils import timezone
# from django_filters.rest_framework import DjangoFilterBackend
# import logging

# from .models import Loan, LoanRepayment, LoanRequest, LoanSettings
# from .serializers import (
#     LoanSerializer, LoanCreateSerializer,
#     LoanRepaymentSerializer, LoanRepaymentCreateSerializer,
#     LoanRequestSerializer, LoanRequestCreateSerializer,
#     LoanSettingsSerializer
# )
# from apps.accounts.models import UserActivityLog
# from apps.notifications.services import NotificationService

# logger = logging.getLogger(__name__)


# class LoanViewSet(viewsets.ModelViewSet):
#     """ViewSet for managing loans"""
#     serializer_class = LoanSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['status', 'loan_type', 'group']
#     search_fields = ['member__full_name', 'purpose']
#     ordering_fields = ['created_at', 'due_date', 'amount']

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return Loan.objects.none()

#         user = self.request.user
#         if user.role == 'admin':
#             return Loan.objects.all()
#         groups = user.chairman_groups.all() | user.secretary_groups.all()
#         return Loan.objects.filter(group__in=groups)

#     def create(self, request):
#         """Create a new loan with unified interest rate"""
#         serializer = LoanCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         member = serializer.validated_data['member']
#         group = member.group
#         loan_type = serializer.validated_data.get('loan_type', 'group_loan')
#         amount = serializer.validated_data['amount']

#         if not member.is_active:
#             return Response(
#                 {'error': 'Member is not active'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         if not group.is_active:
#             return Response(
#                 {'error': 'Group must be active to request loans'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             loan_settings = LoanSettings.objects.get(group=group)

#             interest_rate = loan_settings.default_interest_rate

#             if loan_type == 'group_loan':
#                 duration_months = loan_settings.group_loan_duration_months
#                 max_amount = loan_settings.group_loan_max_amount
#                 min_amount = loan_settings.group_loan_min_amount
#             else: 
#                 duration_months = loan_settings.ecoret_loan_duration_months
#                 max_amount = loan_settings.ecoret_loan_max_amount
#                 min_amount = loan_settings.ecoret_loan_min_amount

#         except LoanSettings.DoesNotExist:
#             return Response(
#                 {'error': 'Loan settings not configured for this group. Please ask the chairman to set up loan settings.'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if amount < min_amount:
#             return Response(
#                 {'error': f'Minimum loan amount is MK{min_amount:,.2f}'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if amount > max_amount:
#             return Response(
#                 {'error': f'Maximum loan amount is MK{max_amount:,.2f}'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         total_payable = amount * (1 + interest_rate / 100)

#         loan = Loan.objects.create(
#             group=group,
#             member=member,
#             created_by=request.user,
#             loan_type=loan_type,
#             amount=amount,
#             interest_rate=interest_rate,
#             duration_months=duration_months,
#             total_payable=total_payable,
#             due_date=timezone.now() + timezone.timedelta(days=duration_months * 30),
#             purpose=serializer.validated_data.get('purpose', ''),
#             status='pending'
#         )

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='create_loan',
#             details={
#                 'loan_id': str(loan.id),
#                 'amount': str(loan.amount),
#                 'interest_rate': str(interest_rate),
#                 'duration_months': duration_months
#             }
#         )

#         return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)

#     @action(detail=True, methods=['post'])
#     def approve(self, request, pk=None):
#         """Approve a pending loan"""
#         loan = self.get_object()
#         if loan.status != 'pending':
#             return Response(
#                 {'error': 'Loan is not pending'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         loan.approve(request.user)

#         notification = NotificationService()
#         notification.send_loan_approval_notification(loan)

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='approve_loan',
#             details={'loan_id': str(loan.id)}
#         )

#         return Response({'message': 'Loan approved successfully'})

#     @action(detail=True, methods=['post'])
#     def decline(self, request, pk=None):
#         """Decline a pending loan"""
#         loan = self.get_object()
#         if loan.status != 'pending':
#             return Response(
#                 {'error': 'Loan is not pending'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         loan.status = 'declined'
#         loan.save()

#         return Response({'message': 'Loan declined successfully'})

#     @action(detail=True, methods=['post'])
#     def disburse(self, request, pk=None):
#         """Disburse an approved loan"""
#         loan = self.get_object()
#         if loan.status != 'approved':
#             return Response(
#                 {'error': 'Loan must be approved first'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         loan.status = 'active'
#         loan.save()

#         return Response({'message': 'Loan disbursed successfully'})

#     @action(detail=True, methods=['post'])
#     def record_repayment(self, request, pk=None):
#         """Record a loan repayment"""
#         loan = self.get_object()
#         if loan.status not in ['active', 'approved']:
#             return Response(
#                 {'error': 'Cannot make repayment on this loan'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = LoanRepaymentCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         amount = serializer.validated_data['amount']
#         balance = loan.get_balance()

#         if amount > balance:
#             return Response(
#                 {'error': f'Amount exceeds balance. Balance: {balance}'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0
#         remaining_principal = loan.total_payable - total_paid

#         if amount <= remaining_principal:
#             principal_paid = amount
#             interest_paid = 0
#         else:
#             principal_paid = remaining_principal
#             interest_paid = amount - remaining_principal

#         repayment = LoanRepayment.objects.create(
#             loan=loan,
#             member=loan.member,
#             recorded_by=request.user,
#             principal_paid=principal_paid,
#             interest_paid=interest_paid,
#             **serializer.validated_data
#         )

#         if loan.get_balance() <= 0:
#             loan.status = 'completed'
#             loan.save()

#         return Response(LoanRepaymentSerializer(repayment).data, status=status.HTTP_201_CREATED)

#     @action(detail=True, methods=['get'])
#     def balance(self, request, pk=None):
#         """Get loan balance"""
#         loan = self.get_object()
#         balance = loan.get_balance()
#         total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0

#         return Response({
#             'total_payable': loan.total_payable,
#             'total_paid': total_paid,
#             'balance': balance,
#             'is_completed': balance <= 0
#         })

#     @action(detail=True, methods=['get'])
#     def repayments(self, request, pk=None):
#         """Get loan repayment history"""
#         loan = self.get_object()
#         repayments = loan.repayments.all()
#         serializer = LoanRepaymentSerializer(repayments, many=True)
#         return Response(serializer.data)


# class LoanRequestViewSet(viewsets.ModelViewSet):
#     """ViewSet for ECORET loan requests"""
#     serializer_class = LoanRequestSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter]
#     filterset_fields = ['status', 'group']
#     search_fields = ['group__group_name', 'purpose']

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return LoanRequest.objects.none()

#         if self.request.user.role == 'admin':
#             return LoanRequest.objects.all()
#         groups = self.request.user.chairman_groups.all()
#         return LoanRequest.objects.filter(group__in=groups)

#     def create(self, request):
#         """Create an ECORET loan request"""
#         groups = request.user.chairman_groups.all()
#         if not groups.exists():
#             return Response(
#                 {'error': 'You must be a group chairman to request a loan'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         group = groups.first()

#         serializer = LoanRequestCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         loan_request = LoanRequest.objects.create(
#             group=group,
#             requested_by=request.user,
#             **serializer.validated_data
#         )

#         notification = NotificationService()
#         notification.send_new_loan_request_notification(loan_request)

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='request_loan',
#             details={'request_id': str(loan_request.id)}
#         )

#         return Response(LoanRequestSerializer(loan_request).data, status=status.HTTP_201_CREATED)

#     @action(detail=True, methods=['post'])
#     def approve(self, request, pk=None):
#         """Approve an ECORET loan request (Admin only)"""
#         if request.user.role != 'admin':
#             return Response(
#                 {'error': 'Only ECORET admin can approve loan requests'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         loan_request = self.get_object()
#         if loan_request.status != 'pending':
#             return Response(
#                 {'error': 'Request is not pending'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         loan_request.approve(request.user)

#         chairman = loan_request.group.chairman
#         if not chairman:
#             return Response(
#                 {'error': 'Group has no chairman'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         member = loan_request.group.members.filter(user=chairman).first()
#         if not member:
#             return Response(
#                 {'error': 'Chairman not found in group members'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         amount = loan_request.amount

#         from .models import ECORETSettings
#         ecoret_settings = ECORETSettings.objects.first()
#         if not ecoret_settings:
#             return Response(
#                 {'error': 'ECORET settings not configured. Contact admin.'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         interest_rate = ecoret_settings.ecoret_loan_interest_rate
#         duration_months = ecoret_settings.ecoret_loan_duration_months
#         max_amount = ecoret_settings.ecoret_loan_max_amount
#         min_amount = ecoret_settings.ecoret_loan_min_amount

#         if amount < min_amount:
#             return Response(
#                 {'error': f'ECORET minimum loan is MK{min_amount:,.2f}'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         if amount > max_amount:
#             return Response(
#                 {'error': f'ECORET maximum loan is MK{max_amount:,.2f}'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         Loan.objects.create(
#             group=loan_request.group,
#             member=member,
#             loan_type='ecoret_loan',
#             amount=amount,
#             interest_rate=interest_rate,
#             total_payable=amount * (1 + interest_rate / 100),
#             duration_months=duration_months,
#             purpose=loan_request.purpose,
#             status='approved',
#             approved_by=request.user,
#             due_date=timezone.now() + timezone.timedelta(days=duration_months * 30)
#         )

#         notification = NotificationService()
#         notification.send_loan_request_approved_notification(loan_request)

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='approve_ecoret_loan',
#             details={
#                 'request_id': str(loan_request.id),
#                 'amount': str(amount),
#                 'interest_rate': str(interest_rate),
#                 'duration_months': duration_months
#             }
#         )

#         return Response({'message': 'Loan request approved'})

#     @action(detail=True, methods=['post'])
#     def decline(self, request, pk=None):
#         """Decline an ECORET loan request (Admin only)"""
#         if request.user.role != 'admin':
#             return Response(
#                 {'error': 'Only ECORET admin can decline loan requests'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         loan_request = self.get_object()
#         if loan_request.status != 'pending':
#             return Response(
#                 {'error': 'Request is not pending'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         loan_request.decline(request.user)

#         return Response({'message': 'Loan request declined'})


# class LoanSettingsViewSet(viewsets.ModelViewSet):
#     """ViewSet for loan settings"""
#     serializer_class = LoanSettingsSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return LoanSettings.objects.none()

#         if self.request.user.role == 'admin':
#             return LoanSettings.objects.all()
#         groups = self.request.user.chairman_groups.all()
#         return LoanSettings.objects.filter(group__in=groups)

#     def create(self, request):
#         """Create loan settings for a group"""
      
#         group = request.user.chairman_groups.first()
#         if not group:
#             return Response(
#                 {'error': 'You must be a chairman to set loan settings'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         if LoanSettings.objects.filter(group=group).exists():
#             return Response(
#                 {'error': 'Loan settings already exist for this group'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = LoanSettingsSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         validated_data = serializer.validated_data.copy()
#         validated_data.pop('group', None)

#         settings = LoanSettings.objects.create(
#             group=group,
#             **validated_data
#         )

#         return Response(LoanSettingsSerializer(settings).data, status=status.HTTP_201_CREATED)

#     @action(detail=True, methods=['put'])
#     def update_settings(self, request, pk=None):
#         """Update loan settings for a group"""
#         settings = self.get_object()
#         serializer = LoanSettingsSerializer(settings, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='update_loan_settings',
#             details={'group_id': str(settings.group.id)}
#         )

#         return Response(serializer.data)
from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
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
    ECORETSettingsSerializer,ECORETBankAccountSerializer 
)
from apps.accounts.models import UserActivityLog
from apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)


class LoanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loans"""
    serializer_class = LoanSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'loan_type', 'group']
    search_fields = ['member__full_name', 'purpose']
    ordering_fields = ['created_at', 'due_date', 'amount']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Loan.objects.none()

        user = self.request.user
        if user.role == 'admin':
            return Loan.objects.all()
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return Loan.objects.filter(group__in=groups)

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

        # ==================== LOAN LIMIT VALIDATION ====================
        
        # Check if member already has an active or approved personal loan
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
        
        # Check if group already has an active or approved ECORET loan
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

        # ==================== LOAN SETTINGS ====================

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
        """Approve a pending loan"""
        loan = self.get_object()
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan.approve(request.user)

        notification = NotificationService()
        notification.send_loan_approval_notification(loan)

        UserActivityLog.objects.create(
            user=request.user,
            action='approve_loan',
            details={'loan_id': str(loan.id)}
        )

        return Response({'message': 'Loan approved successfully'})

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """Decline a pending loan"""
        loan = self.get_object()
        if loan.status != 'pending':
            return Response(
                {'error': 'Loan is not pending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan.status = 'declined'
        loan.save()

        return Response({'message': 'Loan declined successfully'})

    # ==================== ECORET DISBURSEMENT METHODS ====================

    @action(detail=True, methods=['get'])
    def available_accounts(self, request, pk=None):
        """Get available ECORET bank accounts for disbursement"""
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
        
        # Get group bank details for verification
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
        """ECORET Admin: Disburse loan via cash"""
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
        """ECORET Admin: Disburse loan via bank transfer (with PIN verification)"""
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
        
        # Check if group has bank details
        if not loan.group.bank_account_number:
            return Response(
                {'error': 'This group has not set up bank details. Please ask the chairman to add bank details.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = LoanDisbursementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get the selected ECORET account
        account_id = data.get('bank_account_id')
        try:
            account = ECORETBankAccount.objects.get(id=account_id, status='active')
        except ECORETBankAccount.DoesNotExist:
            return Response(
                {'error': 'Invalid bank account selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check account balance
        if account.balance < loan.amount:
            return Response(
                {'error': f'Insufficient balance in {account.name}. Available: MK{account.balance:,.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Note: PIN is passed to PayChangu but NOT stored
        pin = data.get('pin')
        reference = data.get('transfer_reference')
        
        # Deduct from ECORET account
        account.balance -= loan.amount
        account.save()
        
        # Mark loan as disbursed
        loan.mark_as_disbursed_by_ecoret(
            'bank_transfer', 
            user, 
            account=account,
            reference=reference
        )
        
        UserActivityLog.objects.create(
            user=user,
            action='ecoret_disburse_bank_transfer',
            details={
                'loan_id': str(loan.id),
                'amount': str(loan.amount),
                'account': account.name,
                'account_number': account.account_number,
                'reference': reference,
                'group': loan.group.group_name
            }
        )
        
        return Response({
            'message': f'Loan disbursed via bank transfer from {account.name}',
            'transfer_reference': reference,
            'remaining_balance': float(account.balance),
            'loan': LoanSerializer(loan).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def disburse_wait(self, request, pk=None):
        """ECORET Admin: Mark loan as waiting for disbursement"""
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
        
        # Send notification to group chairman
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

    # ==================== CHAIRMAN DISBURSEMENT METHODS ====================

    @action(detail=True, methods=['get'])
    def member_bank_details(self, request, pk=None):
        """Get member bank details for chairman disbursement"""
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
        """Chairman: Disburse cash to member"""
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
        """Chairman: Disburse via bank transfer to member"""
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
        """Chairman: Disburse via mobile money to member"""
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
        """Chairman: Mark loan as waiting for disbursement"""
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
        
        # Send notification to member
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

    # ==================== REPAYMENT METHODS ====================

    @action(detail=True, methods=['post'])
    def record_repayment(self, request, pk=None):
        """Record a loan repayment"""
        loan = self.get_object()
        if loan.status not in ['active', 'approved']:
            return Response(
                {'error': 'Cannot make repayment on this loan'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = LoanRepaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        balance = loan.get_balance()

        if amount > balance:
            return Response(
                {'error': f'Amount exceeds balance. Balance: {balance}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        total_paid = loan.repayments.aggregate(total=Sum('amount'))['total'] or 0
        remaining_principal = loan.total_payable - total_paid

        if amount <= remaining_principal:
            principal_paid = amount
            interest_paid = 0
        else:
            principal_paid = remaining_principal
            interest_paid = amount - remaining_principal

        repayment = LoanRepayment.objects.create(
            loan=loan,
            member=loan.member,
            recorded_by=request.user,
            principal_paid=principal_paid,
            interest_paid=interest_paid,
            **serializer.validated_data
        )

        if loan.get_balance() <= 0:
            loan.status = 'completed'
            loan.save()

        return Response(LoanRepaymentSerializer(repayment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get loan balance"""
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
        """Get loan repayment history"""
        loan = self.get_object()
        repayments = loan.repayments.all()
        serializer = LoanRepaymentSerializer(repayments, many=True)
        return Response(serializer.data)


class LoanRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for ECORET loan requests"""
    serializer_class = LoanRequestSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'group']
    search_fields = ['group__group_name', 'purpose']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return LoanRequest.objects.none()

        if self.request.user.role == 'admin':
            return LoanRequest.objects.all()
        groups = self.request.user.chairman_groups.all()
        return LoanRequest.objects.filter(group__in=groups)

    def create(self, request):
        """Create an ECORET loan request"""
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
        """Approve an ECORET loan request (Admin only)"""
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

        loan_request.approve(request.user)

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

        amount = loan_request.amount

        from .models import ECORETSettings
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

        # Create the loan with 'approved' status (waiting for disbursement)
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

        notification = NotificationService()
        notification.send_loan_request_approved_notification(loan_request)

        UserActivityLog.objects.create(
            user=request.user,
            action='approve_ecoret_loan',
            details={
                'request_id': str(loan_request.id),
                'loan_id': str(loan.id),
                'amount': str(amount),
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
        """Decline an ECORET loan request (Admin only)"""
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
    """ViewSet for loan settings"""
    serializer_class = LoanSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return LoanSettings.objects.none()

        if self.request.user.role == 'admin':
            return LoanSettings.objects.all()
        groups = self.request.user.chairman_groups.all()
        return LoanSettings.objects.filter(group__in=groups)

    def create(self, request):
        """Create loan settings for a group"""
      
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
        """Update loan settings for a group"""
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
    serializer_class =ECORETSettingsSerializer 
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
    Only ECORET Admin can access this
    """
    queryset = ECORETBankAccount.objects.all()
    serializer_class = ECORETBankAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return ECORETBankAccount.objects.all()
        return ECORETBankAccount.objects.none()
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """
        Set a bank account as the default account
        """
        account = self.get_object()
        
        # Set all other accounts to not default
        ECORETBankAccount.objects.filter(is_default=True).update(is_default=False)
        
        # Set this account as default
        account.is_default = True
        account.save()
        
        return Response({
            'message': f'{account.name} set as default account successfully',
            'account': ECORETBankAccountSerializer(account).data
        })
