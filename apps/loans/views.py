from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
import logging

from .models import Loan, LoanRepayment, LoanRequest, LoanSettings
from .serializers import (
    LoanSerializer, LoanCreateSerializer,
    LoanRepaymentSerializer, LoanRepaymentCreateSerializer,
    LoanRequestSerializer, LoanRequestCreateSerializer,
    LoanSettingsSerializer
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
        """Create a new loan with unified interest rate"""
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

    @action(detail=True, methods=['post'])
    def disburse(self, request, pk=None):
        """Disburse an approved loan"""
        loan = self.get_object()
        if loan.status != 'approved':
            return Response(
                {'error': 'Loan must be approved first'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loan.status = 'active'
        loan.save()

        return Response({'message': 'Loan disbursed successfully'})

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

        Loan.objects.create(
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
                'amount': str(amount),
                'interest_rate': str(interest_rate),
                'duration_months': duration_months
            }
        )

        return Response({'message': 'Loan request approved'})

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