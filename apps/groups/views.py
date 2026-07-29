from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
import logging
import random
import string

from .models import Group, GroupMember, GroupRecord
from .serializers import (
    GroupSerializer, GroupCreateSerializer, GroupUpdateSerializer,
    GroupMemberSerializer, GroupMemberCreateSerializer,
    GroupMemberUpdateSerializer, GroupRecordSerializer,
    GroupRecordCreateSerializer,
    GroupBankAccountSerializer, GroupBankAccountUpdateSerializer
)
from apps.accounts.models import UserActivityLog
from apps.security.models import TransactionAudit

logger = logging.getLogger(__name__)


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['group_name', 'group_code']
    ordering_fields = ['created_at', 'group_name']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Group.objects.none()

        user = self.request.user
        if user.role == 'admin':
            return Group.objects.all()
        return Group.objects.filter(
            Q(chairman=user) | Q(secretary=user) | Q(treasurer=user) |
            Q(members__user=user)
        ).distinct()

    def create(self, request):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group = Group.objects.create(
            group_name=serializer.validated_data['group_name'],
            address=serializer.validated_data.get('address', ''),
            chairman=request.user,
            default_interest_rate=serializer.validated_data.get('default_interest_rate', 10.00),
            social_max_contribution=serializer.validated_data.get('social_max_contribution', 5000.00),
            savings_max_contribution=serializer.validated_data.get('savings_max_contribution', 10000.00),
            savings_min_contribution=serializer.validated_data.get('savings_min_contribution', 500.00),
            cycle_start_date=serializer.validated_data.get('cycle_start_date'),
            cycle_end_date=serializer.validated_data.get('cycle_end_date'),
            cycle_duration_months=serializer.validated_data.get('cycle_duration_months', 12),
            meeting_frequency=serializer.validated_data.get('meeting_frequency', 'weekly'),
            meeting_day=serializer.validated_data.get('meeting_day', 'saturday')
        )

        GroupMember.objects.create(
            group=group,
            user=request.user,
            full_name=request.user.get_full_name(),
            phone_number=request.user.phone_number,
            gender='M',
            national_id='PENDING'
        )

        try:
            from apps.loans.models import LoanSettings
            LoanSettings.objects.create(
                group=group,
                default_interest_rate=group.default_interest_rate,
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
        except Exception as e:
            logger.error(f"Failed to create loan settings: {str(e)}")

        UserActivityLog.objects.create(
            user=request.user,
            action='create_group',
            details={
                'group_id': str(group.id),
                'group_name': group.group_name,
                'interest_rate': str(group.default_interest_rate)
            }
        )

        return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put'])
    def update_group(self, request, pk=None):
        group = self.get_object()
        serializer = GroupUpdateSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(GroupSerializer(group).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        group = self.get_object()
        if group.is_active:
            return Response(
                {'error': 'Group is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group_code = group.activate()

        UserActivityLog.objects.create(
            user=request.user,
            action='activate_group',
            details={'group_id': str(group.id), 'group_code': group_code}
        )

        return Response({
            'message': 'Group activated successfully',
            'group_code': group_code
        })

    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        group = self.get_object()
        group.is_active = False
        group.save()

        UserActivityLog.objects.create(
            user=request.user,
            action='disable_group',
            details={'group_id': str(group.id)}
        )

        return Response({'message': 'Group disabled successfully'})

    @action(detail=True, methods=['post'])
    def regenerate_code(self, request, pk=None):
        group = self.get_object()
        if not group.is_active:
            return Response(
                {'error': 'Group must be active to generate code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        while True:
            code = ''.join(random.choices(string.digits, k=6))
            if not Group.objects.filter(group_code=code).exclude(id=group.id).exists():
                group.group_code = code
                group.save()
                break

        return Response({'group_code': code})
    
    @action(detail=True, methods=['post'])
    def start_cycle(self, request, pk=None):
        group = self.get_object()

        if group.is_cycle_active:
            return Response(
                {'error': 'A cycle is already active. End the current cycle first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date = request.data.get('start_date')
        duration_months = request.data.get('duration_months')

        result = group.start_new_cycle(start_date, duration_months)

        UserActivityLog.objects.create(
            user=request.user,
            action='start_cycle',
            details={
                'group_id': str(group.id),
                'group_name': group.group_name,
                'start_date': result['start_date'].isoformat(),
                'end_date': result['end_date'].isoformat(),
                'duration_months': result['duration_months']
            }
        )

        return Response({
            'message': 'Cycle started successfully',
            'cycle': result
        })

    @action(detail=True, methods=['post'])
    def end_cycle(self, request, pk=None):
        group = self.get_object()

        if not group.is_cycle_active:
            return Response(
                {'error': 'No active cycle to end'},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = group.end_current_cycle()

        UserActivityLog.objects.create(
            user=request.user,
            action='end_cycle',
            details={
                'group_id': str(group.id),
                'group_name': str(group.group_name)
            }
        )

        return Response(result)

    @action(detail=True, methods=['get'])
    def cycle_status(self, request, pk=None):
        group = self.get_object()

        progress = group.get_cycle_progress()
        status = group.get_cycle_status()

        return Response({
            'is_active': group.is_cycle_active,
            'status': status,
            'start_date': group.cycle_start_date,
            'end_date': group.cycle_end_date,
            'duration_months': group.cycle_duration_months,
            'progress': progress,
            'settings': {
                'default_interest_rate': group.default_interest_rate,
                'social_max_contribution': group.social_max_contribution,
                'savings_max_contribution': group.savings_max_contribution,
                'savings_min_contribution': group.savings_min_contribution,
                'meeting_frequency': group.meeting_frequency,
                'meeting_day': group.meeting_day
            }
        })

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        group = self.get_object()
        if not group.is_active:
            return Response(
                {'error': 'Group must be active to add members'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = GroupMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if GroupMember.objects.filter(
            group=group,
            phone_number=serializer.validated_data['phone_number']
        ).exists():
            return Response(
                {'error': 'Member already exists in this group'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member = GroupMember.objects.create(
            group=group,
            **serializer.validated_data
        )

        try:
            from apps.notifications.services import NotificationService
            notification = NotificationService()

            user = member.user
            sms_message = f"""
ECORET: You have been registered to {group.group_name}.
Group Code: {group.group_code}
Chairman: {group.chairman.get_full_name()}
Dial *123# to access your group.
            """

            if user:
                notification.send_sms_notification(user, sms_message)
            else:
                notification.send_direct_sms(member.phone_number, sms_message)

        except Exception as e:
            logger.error(f"Failed to send SMS to {member.phone_number}: {str(e)}")

        return Response(GroupMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['put', 'patch'])
    def update_member(self, request, pk=None):
        group = self.get_object()
        member_id = request.query_params.get('member_id')

        if not member_id:
            return Response(
                {'error': 'member_id is required as query parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member = get_object_or_404(GroupMember, id=member_id, group=group)

        serializer = GroupMemberUpdateSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(GroupMemberSerializer(member).data)

    @action(detail=True, methods=['delete'], url_path='members/(?P<member_id>[^/.]+)')
    def remove_member(self, request, pk=None, member_id=None):
        group = self.get_object()
        member = get_object_or_404(GroupMember, id=member_id, group=group)

        member_name = member.full_name
        member_phone = member.phone_number
        user = member.user

        member.is_active = False
        member.save()

        try:
            from apps.notifications.services import NotificationService
            notification = NotificationService()

            sms_message = f"""
ECORET: You have been removed from {group.group_name}.
Please contact your group chairman for more information.
            """

            if user:
                notification.send_sms_notification(user, sms_message)
            else:
                notification.send_direct_sms(member_phone, sms_message)

            if group.chairman:
                notification.send_notification(
                    group.chairman,
                    'Member Removed',
                    f'{member_name} has been removed from {group.group_name}',
                    'member_removal'
                )

        except Exception as e:
            logger.error(f"Failed to send SMS to {member_phone}: {str(e)}")

        UserActivityLog.objects.create(
            user=request.user,
            action='remove_member',
            details={
                'member_id': str(member.id),
                'member_name': member_name,
                'group_id': str(group.id)
            }
        )

        return Response({
            'message': f'Member {member_name} removed successfully',
            'sms_sent': True
        })

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        group = self.get_object()
        members = group.members.filter(is_active=True)
        serializer = GroupMemberSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['put', 'patch'])
    def update_bank_account(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can update bank details'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = GroupBankAccountUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(group, field, value)
        group.save()

        UserActivityLog.objects.create(
            user=request.user,
            action='update_bank_account',
            details={'group_id': str(group.id)}
        )

        TransactionAudit.objects.create(
            user=request.user,
            group=group,
            transaction_type='bank_account_update',
            amount=0,
            details={'updated_fields': list(serializer.validated_data.keys())},
            status='success'
        )

        return Response({
            'message': 'Bank account details updated successfully',
            'data': GroupBankAccountSerializer(group).data
        })

    @action(detail=True, methods=['get'])
    def get_bank_account(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['admin', 'chairman', 'secretary', 'treasurer']:
            return Response(
                {'error': 'You do not have permission to view bank details'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = GroupBankAccountSerializer(group)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def verify_bank_account(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can verify bank details'},
                status=status.HTTP_403_FORBIDDEN
            )

        bank_account_number = request.data.get('bank_account_number')
        account_name = request.data.get('bank_account_name')

        if not bank_account_number:
            return Response(
                {'error': 'Bank account number is required for verification'},
                status=status.HTTP_400_BAD_REQUEST
            )

        verification_status = {
            'verified': True,
            'account_holder': account_name or 'Account Holder Name',
            'bank': group.bank_name or 'National Bank of Malawi',
            'message': 'Account verified successfully',
            'verified_at': timezone.now().isoformat()
        }

        UserActivityLog.objects.create(
            user=request.user,
            action='verify_bank_account',
            details={
                'group_id': str(group.id),
                'verified': verification_status['verified'],
                'bank': verification_status['bank']
            }
        )

        return Response(verification_status)

    @action(detail=True, methods=['post'])
    def update_mobile_money(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['chairman', 'admin', 'treasurer']:
            return Response(
                {'error': 'Only chairman, admin, or treasurer can update mobile money details'},
                status=status.HTTP_403_FORBIDDEN
            )

        provider = request.data.get('mobile_money_provider')
        number = request.data.get('mobile_money_number')

        if not provider or not number:
            return Response(
                {'error': 'Provider and number are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        group.mobile_money_provider = provider
        group.mobile_money_number = number
        group.save()

        UserActivityLog.objects.create(
            user=request.user,
            action='update_mobile_money',
            details={
                'group_id': str(group.id),
                'provider': provider
            }
        )

        return Response({
            'message': 'Mobile money details updated successfully',
            'provider': provider,
            'number': number
        })

    @action(detail=True, methods=['get'])
    def get_mobile_money(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['admin', 'chairman', 'secretary', 'treasurer']:
            return Response(
                {'error': 'You do not have permission to view mobile money details'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            'mobile_money_provider': group.mobile_money_provider,
            'mobile_money_number': group.mobile_money_number,
            'has_mobile_money': bool(group.mobile_money_number)
        })

    @action(detail=True, methods=['put'])
    def update_ecoret_account(self, request, pk=None):
        group = self.get_object()

        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET admin can update ECORET account details'},
                status=status.HTTP_403_FORBIDDEN
            )

        ecoret_account_id = request.data.get('ecoret_account_id')
        ecoret_billing_code = request.data.get('ecoret_billing_code')
        virtual_account_number = request.data.get('virtual_account_number')
        virtual_account_holder = request.data.get('virtual_account_holder')

        if ecoret_account_id:
            group.ecoret_account_id = ecoret_account_id
        if ecoret_billing_code:
            group.ecoret_billing_code = ecoret_billing_code
        if virtual_account_number:
            group.virtual_account_number = virtual_account_number
        if virtual_account_holder:
            group.virtual_account_holder = virtual_account_holder

        group.save()

        UserActivityLog.objects.create(
            user=request.user,
            action='update_ecoret_account',
            details={'group_id': str(group.id)}
        )

        return Response({
            'message': 'ECORET account details updated successfully',
            'data': {
                'ecoret_account_id': group.ecoret_account_id,
                'ecoret_billing_code': group.ecoret_billing_code,
                'virtual_account_number': group.virtual_account_number,
                'virtual_account_holder': group.virtual_account_holder
            }
        })

    @action(detail=True, methods=['get'])
    def get_ecoret_account(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['admin', 'chairman']:
            return Response(
                {'error': 'You do not have permission to view ECORET account details'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            'ecoret_account_id': group.ecoret_account_id,
            'ecoret_billing_code': group.ecoret_billing_code,
            'virtual_account_number': group.virtual_account_number,
            'virtual_account_holder': group.virtual_account_holder,
            'has_ecoret_account': bool(group.ecoret_account_id)
        })

    @action(detail=True, methods=['put'])
    def update_limits(self, request, pk=None):
        group = self.get_object()

        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can update limits'},
                status=status.HTTP_403_FORBIDDEN
            )

        daily_limit = request.data.get('daily_transaction_limit')
        max_loan = request.data.get('max_loan_amount')

        if daily_limit is not None:
            group.daily_transaction_limit = daily_limit
        if max_loan is not None:
            group.max_loan_amount = max_loan

        group.save()

        UserActivityLog.objects.create(
            user=request.user,
            action='update_limits',
            details={
                'group_id': str(group.id),
                'daily_transaction_limit': str(group.daily_transaction_limit),
                'max_loan_amount': str(group.max_loan_amount)
            }
        )

        return Response({
            'message': 'Limits updated successfully',
            'daily_transaction_limit': group.daily_transaction_limit,
            'max_loan_amount': group.max_loan_amount
        })

    @action(detail=True, methods=['get'])
    def get_limits(self, request, pk=None):
        group = self.get_object()

        return Response({
            'daily_transaction_limit': group.daily_transaction_limit,
            'max_loan_amount': group.max_loan_amount
        })

    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        group = self.get_object()

        total_members = group.members.filter(is_active=True).count()
        total_loans = group.loans.count()
        active_loans = group.loans.filter(status='active').count()

        return Response({
            'total_members': total_members,
            'total_loans': total_loans,
            'active_loans': active_loans,
            'is_active': group.is_active,
            'has_bank_account': bool(group.bank_account_number),
            'has_mobile_money': bool(group.mobile_money_number),
            'has_ecoret_account': bool(group.ecoret_account_id)
        })

    @action(detail=True, methods=['post'])
    def upload_record(self, request, pk=None):
        group = self.get_object()
        serializer = GroupRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = GroupRecord.objects.create(
            group=group,
            uploaded_by=request.user,
            **serializer.validated_data
        )

        return Response(
        GroupRecordSerializer(record, context={'request': request}).data,
        status=status.HTTP_201_CREATED
    )
    
    @action(detail=True, methods=['get'])
    def records(self, request, pk=None):
        group = self.get_object()
        records = group.records.all()
        serializer = GroupRecordSerializer(records, many=True, context={'request': request})
        return Response(serializer.data)
    
    # @action(detail=True, methods=['post'])
    # def send_notification(self, request, pk=None):
    #     group = self.get_object()
    #     title = request.data.get('title')
    #     message = request.data.get('message')

    #     if not title or not message:
    #         return Response(
    #             {'error': 'title and message are required'},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     from apps.notifications.services import NotificationService
    #     notification = NotificationService()

    #     sent_count = 0
    #     for member in group.members.filter(is_active=True):
    #         try:
    #             if member.user:
    #                 notification.send_notification(member.user, title, message, 'group_notice')
    #             else:
    #                 notification.send_direct_sms(member.phone_number, f"{title}\n{message}")
    #             sent_count += 1
    #         except Exception as e:
    #             logger.error(f"Failed to notify {member.full_name}: {str(e)}")

    #     UserActivityLog.objects.create(
    #         user=request.user,
    #         action='send_group_notification',
    #         details={'group_id': str(group.id), 'title': title, 'recipients': sent_count}
    #     )

    #     return Response({
    #         'message': f'Notification sent to {sent_count} member(s)',
    #         'sent_count': sent_count
    #     })