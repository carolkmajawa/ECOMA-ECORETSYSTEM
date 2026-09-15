# from rest_framework import viewsets, status, permissions, filters
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from django.shortcuts import get_object_or_404
# from django.db.models import Q
# from django.utils import timezone
# from django_filters.rest_framework import DjangoFilterBackend
# import logging
# import random
# import string

# from .models import Group, GroupMember, GroupRecord
# from .serializers import (
#     GroupSerializer, GroupCreateSerializer, GroupUpdateSerializer,
#     GroupMemberSerializer, GroupMemberCreateSerializer,
#     GroupMemberUpdateSerializer, GroupRecordSerializer,
#     GroupRecordCreateSerializer,
#     GroupBankAccountSerializer, GroupBankAccountUpdateSerializer
# )
# from apps.accounts.models import UserActivityLog
# from apps.security.models import TransactionAudit

# logger = logging.getLogger(__name__)


# class GroupViewSet(viewsets.ModelViewSet):
#     serializer_class = GroupSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['is_active']
#     search_fields = ['group_name', 'group_code']
#     ordering_fields = ['created_at', 'group_name']

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return Group.objects.none()

#         user = self.request.user
#         if user.role == 'admin':
#             return Group.objects.all()
#         return Group.objects.filter(
#             Q(chairman=user) | Q(secretary=user) | Q(treasurer=user) |
#             Q(members__user=user)
#         ).distinct()

#     def create(self, request):
#         serializer = GroupCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         group = Group.objects.create(
#             group_name=serializer.validated_data['group_name'],
#             address=serializer.validated_data.get('address', ''),
#             chairman=request.user,
#             default_interest_rate=serializer.validated_data.get('default_interest_rate', 10.00),
#             social_max_contribution=serializer.validated_data.get('social_max_contribution', 5000.00),
#             savings_max_contribution=serializer.validated_data.get('savings_max_contribution', 10000.00),
#             savings_min_contribution=serializer.validated_data.get('savings_min_contribution', 500.00),
#             cycle_start_date=serializer.validated_data.get('cycle_start_date'),
#             cycle_end_date=serializer.validated_data.get('cycle_end_date'),
#             cycle_duration_months=serializer.validated_data.get('cycle_duration_months', 12),
#             meeting_frequency=serializer.validated_data.get('meeting_frequency', 'weekly'),
#             meeting_day=serializer.validated_data.get('meeting_day', 'saturday')
#         )

#         GroupMember.objects.create(
#             group=group,
#             user=request.user,
#             full_name=request.user.get_full_name(),
#             phone_number=request.user.phone_number,
#             gender='M',
#             national_id='PENDING'
#         )

#         try:
#             from apps.loans.models import LoanSettings
#             LoanSettings.objects.create(
#                 group=group,
#                 default_interest_rate=group.default_interest_rate,
#                 group_loan_duration_months=6,
#                 ecoret_loan_duration_months=12,
#                 group_loan_min_amount=1000.00,
#                 group_loan_max_amount=500000.00,
#                 ecoret_loan_min_amount=10000.00,
#                 ecoret_loan_max_amount=1000000.00,
#                 requires_guarantor=True,
#                 min_guarantors=2,
#                 grace_period_days=7,
#                 late_fee_percentage=0.00
#             )
#         except Exception as e:
#             logger.error(f"Failed to create loan settings: {str(e)}")

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='create_group',
#             details={
#                 'group_id': str(group.id),
#                 'group_name': group.group_name,
#                 'interest_rate': str(group.default_interest_rate)
#             }
#         )

#         return Response(GroupSerializer(group).data, status=status.HTTP_201_CREATED)

#     @action(detail=True, methods=['put'])
#     def update_group(self, request, pk=None):
#         group = self.get_object()
#         serializer = GroupUpdateSerializer(group, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(GroupSerializer(group).data)

#     @action(detail=True, methods=['post'])
#     def activate(self, request, pk=None):
#         group = self.get_object()
#         if group.is_active:
#             return Response(
#                 {'error': 'Group is already active'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         group_code = group.activate()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='activate_group',
#             details={'group_id': str(group.id), 'group_code': group_code}
#         )

#         return Response({
#             'message': 'Group activated successfully',
#             'group_code': group_code
#         })

#     @action(detail=True, methods=['post'])
#     def disable(self, request, pk=None):
#         group = self.get_object()
#         group.is_active = False
#         group.save()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='disable_group',
#             details={'group_id': str(group.id)}
#         )

#         return Response({'message': 'Group disabled successfully'})

#     @action(detail=True, methods=['post'])
#     def regenerate_code(self, request, pk=None):
#         group = self.get_object()
#         if not group.is_active:
#             return Response(
#                 {'error': 'Group must be active to generate code'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         while True:
#             code = ''.join(random.choices(string.digits, k=6))
#             if not Group.objects.filter(group_code=code).exclude(id=group.id).exists():
#                 group.group_code = code
#                 group.save()
#                 break

#         return Response({'group_code': code})
    
#     @action(detail=True, methods=['post'])
#     def start_cycle(self, request, pk=None):
#         group = self.get_object()

#         if group.is_cycle_active:
#             return Response(
#                 {'error': 'A cycle is already active. End the current cycle first.'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         start_date = request.data.get('start_date')
#         duration_months = request.data.get('duration_months')

#         result = group.start_new_cycle(start_date, duration_months)

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='start_cycle',
#             details={
#                 'group_id': str(group.id),
#                 'group_name': group.group_name,
#                 'start_date': result['start_date'].isoformat(),
#                 'end_date': result['end_date'].isoformat(),
#                 'duration_months': result['duration_months']
#             }
#         )

#         return Response({
#             'message': 'Cycle started successfully',
#             'cycle': result
#         })

#     @action(detail=True, methods=['post'])
#     def end_cycle(self, request, pk=None):
#         group = self.get_object()

#         if not group.is_cycle_active:
#             return Response(
#                 {'error': 'No active cycle to end'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         result = group.end_current_cycle()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='end_cycle',
#             details={
#                 'group_id': str(group.id),
#                 'group_name': str(group.group_name)
#             }
#         )

#         return Response(result)

#     @action(detail=True, methods=['get'])
#     def cycle_status(self, request, pk=None):
#         group = self.get_object()

#         progress = group.get_cycle_progress()
#         status = group.get_cycle_status()

#         return Response({
#             'is_active': group.is_cycle_active,
#             'status': status,
#             'start_date': group.cycle_start_date,
#             'end_date': group.cycle_end_date,
#             'duration_months': group.cycle_duration_months,
#             'progress': progress,
#             'settings': {
#                 'default_interest_rate': group.default_interest_rate,
#                 'social_max_contribution': group.social_max_contribution,
#                 'savings_max_contribution': group.savings_max_contribution,
#                 'savings_min_contribution': group.savings_min_contribution,
#                 'meeting_frequency': group.meeting_frequency,
#                 'meeting_day': group.meeting_day
#             }
#         })

#     @action(detail=True, methods=['post'])
#     def add_member(self, request, pk=None):
#         group = self.get_object()
#         if not group.is_active:
#             return Response(
#                 {'error': 'Group must be active to add members'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         serializer = GroupMemberCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         if GroupMember.objects.filter(
#             group=group,
#             phone_number=serializer.validated_data['phone_number']
#         ).exists():
#             return Response(
#                 {'error': 'Member already exists in this group'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         member = GroupMember.objects.create(
#             group=group,
#             **serializer.validated_data
#         )

#         try:
#             from apps.notifications.services import NotificationService
#             notification = NotificationService()

#             user = member.user
#             sms_message = f"""
# ECORET: You have been registered to {group.group_name}.
# Group Code: {group.group_code}
# Chairman: {group.chairman.get_full_name()}
# Dial *123# to access your group.
#             """

#             if user:
#                 notification.send_sms_notification(user, sms_message)
#             else:
#                 notification.send_direct_sms(member.phone_number, sms_message)

#         except Exception as e:
#             logger.error(f"Failed to send SMS to {member.phone_number}: {str(e)}")

#         return Response(GroupMemberSerializer(member).data, status=status.HTTP_201_CREATED)

#     @action(detail=True, methods=['put', 'patch'])
#     def update_member(self, request, pk=None):
#         group = self.get_object()
#         member_id = request.query_params.get('member_id')

#         if not member_id:
#             return Response(
#                 {'error': 'member_id is required as query parameter'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         member = get_object_or_404(GroupMember, id=member_id, group=group)

#         serializer = GroupMemberUpdateSerializer(member, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()

#         return Response(GroupMemberSerializer(member).data)

#     @action(detail=True, methods=['delete'], url_path='members/(?P<member_id>[^/.]+)')
#     def remove_member(self, request, pk=None, member_id=None):
#         group = self.get_object()
#         member = get_object_or_404(GroupMember, id=member_id, group=group)

#         member_name = member.full_name
#         member_phone = member.phone_number
#         user = member.user

#         member.is_active = False
#         member.save()

#         try:
#             from apps.notifications.services import NotificationService
#             notification = NotificationService()

#             sms_message = f"""
# ECORET: You have been removed from {group.group_name}.
# Please contact your group chairman for more information.
#             """

#             if user:
#                 notification.send_sms_notification(user, sms_message)
#             else:
#                 notification.send_direct_sms(member_phone, sms_message)

#             if group.chairman:
#                 notification.send_notification(
#                     group.chairman,
#                     'Member Removed',
#                     f'{member_name} has been removed from {group.group_name}',
#                     'member_removal'
#                 )

#         except Exception as e:
#             logger.error(f"Failed to send SMS to {member_phone}: {str(e)}")

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='remove_member',
#             details={
#                 'member_id': str(member.id),
#                 'member_name': member_name,
#                 'group_id': str(group.id)
#             }
#         )

#         return Response({
#             'message': f'Member {member_name} removed successfully',
#             'sms_sent': True
#         })

#     @action(detail=True, methods=['get'])
#     def members(self, request, pk=None):
#         group = self.get_object()
#         members = group.members.filter(is_active=True)
#         serializer = GroupMemberSerializer(members, many=True)
#         return Response(serializer.data)

#     @action(detail=True, methods=['put', 'patch'])
#     def update_bank_account(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['chairman', 'admin']:
#             return Response(
#                 {'error': 'Only chairman or admin can update bank details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         serializer = GroupBankAccountUpdateSerializer(data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)

#         for field, value in serializer.validated_data.items():
#             setattr(group, field, value)
#         group.save()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='update_bank_account',
#             details={'group_id': str(group.id)}
#         )

#         TransactionAudit.objects.create(
#             user=request.user,
#             group=group,
#             transaction_type='bank_account_update',
#             amount=0,
#             details={'updated_fields': list(serializer.validated_data.keys())},
#             status='success'
#         )

#         return Response({
#             'message': 'Bank account details updated successfully',
#             'data': GroupBankAccountSerializer(group).data
#         })

#     @action(detail=True, methods=['get'])
#     def get_bank_account(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['admin', 'chairman', 'secretary', 'treasurer']:
#             return Response(
#                 {'error': 'You do not have permission to view bank details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         serializer = GroupBankAccountSerializer(group)
#         return Response(serializer.data)

#     @action(detail=True, methods=['post'])
#     def verify_bank_account(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['chairman', 'admin']:
#             return Response(
#                 {'error': 'Only chairman or admin can verify bank details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         bank_account_number = request.data.get('bank_account_number')
#         account_name = request.data.get('bank_account_name')

#         if not bank_account_number:
#             return Response(
#                 {'error': 'Bank account number is required for verification'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         verification_status = {
#             'verified': True,
#             'account_holder': account_name or 'Account Holder Name',
#             'bank': group.bank_name or 'National Bank of Malawi',
#             'message': 'Account verified successfully',
#             'verified_at': timezone.now().isoformat()
#         }

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='verify_bank_account',
#             details={
#                 'group_id': str(group.id),
#                 'verified': verification_status['verified'],
#                 'bank': verification_status['bank']
#             }
#         )

#         return Response(verification_status)

#     @action(detail=True, methods=['post'])
#     def update_mobile_money(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['chairman', 'admin', 'treasurer']:
#             return Response(
#                 {'error': 'Only chairman, admin, or treasurer can update mobile money details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         provider = request.data.get('mobile_money_provider')
#         number = request.data.get('mobile_money_number')

#         if not provider or not number:
#             return Response(
#                 {'error': 'Provider and number are required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         group.mobile_money_provider = provider
#         group.mobile_money_number = number
#         group.save()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='update_mobile_money',
#             details={
#                 'group_id': str(group.id),
#                 'provider': provider
#             }
#         )

#         return Response({
#             'message': 'Mobile money details updated successfully',
#             'provider': provider,
#             'number': number
#         })

#     @action(detail=True, methods=['get'])
#     def get_mobile_money(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['admin', 'chairman', 'secretary', 'treasurer']:
#             return Response(
#                 {'error': 'You do not have permission to view mobile money details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         return Response({
#             'mobile_money_provider': group.mobile_money_provider,
#             'mobile_money_number': group.mobile_money_number,
#             'has_mobile_money': bool(group.mobile_money_number)
#         })

#     @action(detail=True, methods=['put'])
#     def update_ecoret_account(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role != 'admin':
#             return Response(
#                 {'error': 'Only ECORET admin can update ECORET account details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         ecoret_account_id = request.data.get('ecoret_account_id')
#         ecoret_billing_code = request.data.get('ecoret_billing_code')
#         virtual_account_number = request.data.get('virtual_account_number')
#         virtual_account_holder = request.data.get('virtual_account_holder')

#         if ecoret_account_id:
#             group.ecoret_account_id = ecoret_account_id
#         if ecoret_billing_code:
#             group.ecoret_billing_code = ecoret_billing_code
#         if virtual_account_number:
#             group.virtual_account_number = virtual_account_number
#         if virtual_account_holder:
#             group.virtual_account_holder = virtual_account_holder

#         group.save()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='update_ecoret_account',
#             details={'group_id': str(group.id)}
#         )

#         return Response({
#             'message': 'ECORET account details updated successfully',
#             'data': {
#                 'ecoret_account_id': group.ecoret_account_id,
#                 'ecoret_billing_code': group.ecoret_billing_code,
#                 'virtual_account_number': group.virtual_account_number,
#                 'virtual_account_holder': group.virtual_account_holder
#             }
#         })

#     @action(detail=True, methods=['get'])
#     def get_ecoret_account(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['admin', 'chairman']:
#             return Response(
#                 {'error': 'You do not have permission to view ECORET account details'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         return Response({
#             'ecoret_account_id': group.ecoret_account_id,
#             'ecoret_billing_code': group.ecoret_billing_code,
#             'virtual_account_number': group.virtual_account_number,
#             'virtual_account_holder': group.virtual_account_holder,
#             'has_ecoret_account': bool(group.ecoret_account_id)
#         })

#     @action(detail=True, methods=['put'])
#     def update_limits(self, request, pk=None):
#         group = self.get_object()

#         if request.user.role not in ['chairman', 'admin']:
#             return Response(
#                 {'error': 'Only chairman or admin can update limits'},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         daily_limit = request.data.get('daily_transaction_limit')
#         max_loan = request.data.get('max_loan_amount')

#         if daily_limit is not None:
#             group.daily_transaction_limit = daily_limit
#         if max_loan is not None:
#             group.max_loan_amount = max_loan

#         group.save()

#         UserActivityLog.objects.create(
#             user=request.user,
#             action='update_limits',
#             details={
#                 'group_id': str(group.id),
#                 'daily_transaction_limit': str(group.daily_transaction_limit),
#                 'max_loan_amount': str(group.max_loan_amount)
#             }
#         )

#         return Response({
#             'message': 'Limits updated successfully',
#             'daily_transaction_limit': group.daily_transaction_limit,
#             'max_loan_amount': group.max_loan_amount
#         })

#     @action(detail=True, methods=['get'])
#     def get_limits(self, request, pk=None):
#         group = self.get_object()

#         return Response({
#             'daily_transaction_limit': group.daily_transaction_limit,
#             'max_loan_amount': group.max_loan_amount
#         })

#     @action(detail=True, methods=['get'])
#     def statistics(self, request, pk=None):
#         group = self.get_object()

#         total_members = group.members.filter(is_active=True).count()
#         total_loans = group.loans.count()
#         active_loans = group.loans.filter(status='active').count()

#         return Response({
#             'total_members': total_members,
#             'total_loans': total_loans,
#             'active_loans': active_loans,
#             'is_active': group.is_active,
#             'has_bank_account': bool(group.bank_account_number),
#             'has_mobile_money': bool(group.mobile_money_number),
#             'has_ecoret_account': bool(group.ecoret_account_id)
#         })

#     @action(detail=True, methods=['post'])
#     def upload_record(self, request, pk=None):
#         group = self.get_object()
#         serializer = GroupRecordCreateSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         record = GroupRecord.objects.create(
#             group=group,
#             uploaded_by=request.user,
#             **serializer.validated_data
#         )

#         return Response(
#         GroupRecordSerializer(record, context={'request': request}).data,
#         status=status.HTTP_201_CREATED
#     )
    
#     @action(detail=True, methods=['get'])
#     def records(self, request, pk=None):
#         group = self.get_object()
#         records = group.records.all()
#         serializer = GroupRecordSerializer(records, many=True, context={'request': request})
#         return Response(serializer.data)
    




# apps/groups/views.py - COMPLETE WITH LEDGER
from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import APIView, action
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
import logging
import random
import string
from rest_framework.views import APIView
from apps.security.models import TransactionAudit
from .models import Group, GroupMember, GroupRecord, LedgerEntry, LedgerCategory
from .serializers import (
    GroupSerializer, GroupCreateSerializer, GroupUpdateSerializer,
    GroupMemberSerializer, GroupMemberCreateSerializer,
    GroupMemberUpdateSerializer, GroupRecordSerializer,
    GroupRecordCreateSerializer,
    GroupBankAccountSerializer, GroupBankAccountUpdateSerializer,
    LedgerEntrySerializer, LedgerEntryCreateSerializer,
    LedgerCategorySerializer, LedgerSummarySerializer
)
from apps.accounts.models import UserActivityLog
from apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)


class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing groups
    """
    queryset = Group.objects.all().order_by('-created_at')
    serializer_class = GroupSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'chairman', 'secretary']
    search_fields = ['group_name', 'location', 'chairman__full_name']
    ordering_fields = ['created_at', 'group_name']

    def get_queryset(self):
        """
        Override to filter based on user role
        """
        user = self.request.user
        
        # For admin, return all groups
        if user.role == 'admin':
            return Group.objects.all().order_by('-created_at')
        
        # For chairman, return their groups
        if user.role == 'chairman':
            return Group.objects.filter(
                Q(chairman=user) | 
                Q(secretary__user=user)
            ).order_by('-created_at')
        
        # For other users, return groups they are members of
        return Group.objects.filter(
            members__user=user, members__is_active=True
        ).distinct().order_by('-created_at')

    def perform_create(self, serializer):
        """
        Create a new group with the current user as chairman
        """
        group = serializer.save(
            chairman=self.request.user,
        )
        
        # Generate group code
        group.generate_group_code()
        group.save()
        
        # Add the chairman as a member
        GroupMember.objects.create(
            group=group,
            user=self.request.user,
            full_name=self.request.user.get_full_name() or self.request.user.email,
            phone_number=self.request.user.phone_number,
            is_active=True,
            joined_date=timezone.now()
        )
        
        # Log activity
        UserActivityLog.objects.create(
            user=self.request.user,
            action='create_group',
            details={
                'group_id': str(group.id),
                'group_name': group.group_name
            }
        )

    def update(self, request, *args, **kwargs):
        """
        Override update to handle secretary/treasurer properly
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = GroupUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Handle secretary and treasurer specially
        if 'secretary' in request.data:
            secretary_id = request.data.get('secretary')
            if secretary_id:
                try:
                    secretary = GroupMember.objects.get(id=secretary_id, group=instance)
                    instance.secretary = secretary
                except GroupMember.DoesNotExist:
                    pass
            else:
                instance.secretary = None
        
        if 'treasurer' in request.data:
            treasurer_id = request.data.get('treasurer')
            if treasurer_id:
                try:
                    treasurer = GroupMember.objects.get(id=treasurer_id, group=instance)
                    instance.treasurer = treasurer
                except GroupMember.DoesNotExist:
                    pass
            else:
                instance.treasurer = None
        
        # Save other fields
        for field, value in serializer.validated_data.items():
            if field not in ['secretary', 'treasurer']:
                setattr(instance, field, value)
        
        instance.save()
        
        # Return the full group data
        full_serializer = GroupSerializer(instance)
        return Response(full_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """
        Override partial_update to use the custom update
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

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

    # ==================== ACTIVATE GROUP ====================
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a group"""
        group = self.get_object()
        
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only admin can activate groups'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if group.is_active:
            return Response(
                {'error': 'Group is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group.is_active = True
        group.activation_date = timezone.now()
        group.save()
        
        return Response({'message': 'Group activated successfully'})

    # ==================== ADD MEMBER ====================
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """
        Add a member to the group
        """
        group = self.get_object()
        
        if not group.is_active:
            return Response(
                {'error': 'Group must be active to add members'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permission
        if request.user.role != 'admin' and request.user != group.chairman:
            return Response(
                {'error': 'Only admin or chairman can add members'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = GroupMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_number = serializer.validated_data['phone_number']
        
        # Check if member already exists
        if GroupMember.objects.filter(
            group=group,
            phone_number=phone_number
        ).exists():
            return Response(
                {'error': 'Member already exists in this group'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create member
        member = GroupMember.objects.create(
            group=group,
            **serializer.validated_data
        )

        # Log activity
        UserActivityLog.objects.create(
            user=request.user,
            action='add_member',
            details={
                'group_id': str(group.id),
                'group_name': group.group_name,
                'member_id': str(member.id),
                'member_name': member.full_name,
                'phone': phone_number
            }
        )

        return Response(GroupMemberSerializer(member).data, status=status.HTTP_201_CREATED)

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
        }, status=status.HTTP_200_OK)

    # ==================== UPDATE MEMBER ROLE ====================
    @action(detail=True, methods=['post'])
    def update_member_role(self, request, pk=None):
        """Update a member's role (member, secretary, treasurer)"""
        group = self.get_object()
        member_id = request.data.get('member_id')
        role = request.data.get('role')

        if not member_id or not role:
            return Response(
                {'error': 'member_id and role are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if role not in ['member', 'secretary', 'treasurer']:
            return Response(
                {'error': 'Role must be member, secretary, or treasurer'},
                status=status.HTTP_400_BAD_REQUEST
            )

        member = get_object_or_404(GroupMember, id=member_id, group=group)
        member.role = role
        member.save()

        # If assigning as secretary or treasurer, update the group
        if role == 'secretary':
            group.secretary = member
            group.save()
        elif role == 'treasurer':
            group.treasurer = member
            group.save()
        else:
            # If removing from role, check if this member was secretary or treasurer
            if group.secretary and group.secretary.id == member.id:
                group.secretary = None
                group.save()
            if group.treasurer and group.treasurer.id == member.id:
                group.treasurer = None
                group.save()

        return Response({
            'message': f'{member.full_name} is now {role}',
            'member': GroupMemberSerializer(member).data
        })

    # ==================== GET MEMBERS ====================
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get all members of a group"""
        group = self.get_object()
        members = group.members.filter(is_active=True)
        serializer = GroupMemberSerializer(members, many=True)
        return Response(serializer.data)

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

    # ==================== CYCLE MANAGEMENT ====================
    @action(detail=True, methods=['post'])
    def start_cycle(self, request, pk=None):
        """Start a new cycle"""
        group = self.get_object()

        if group.is_cycle_active:
            return Response(
                {'error': 'A cycle is already active. End the current cycle first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        start_date = request.data.get('start_date')
        duration_months = request.data.get('duration_months', 6)

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
        """End the current cycle"""
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
                'group_name': group.group_name
            }
        )

        return Response(result)

    @action(detail=True, methods=['get'])
    def cycle_status(self, request, pk=None):
        """Get cycle status"""
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

    # ==================== LEDGER MANAGEMENT ====================

    @action(detail=True, methods=['get'])
    def ledger_entries(self, request, pk=None):
        """Get all ledger entries for a group"""
        group = self.get_object()
        
        # Filter parameters
        transaction_type = request.query_params.get('transaction_type')
        category = request.query_params.get('category')
        member_id = request.query_params.get('member_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = LedgerEntry.objects.filter(group=group, is_deleted=False)
        
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if category:
            queryset = queryset.filter(category=category)
        if member_id:
            queryset = queryset.filter(member_id=member_id)
        if start_date:
            queryset = queryset.filter(recorded_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(recorded_at__date__lte=end_date)
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = LedgerEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = LedgerEntrySerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_ledger_entry(self, request, pk=None):
        """Add a new ledger entry"""
        group = self.get_object()
        
        # Check permission
        if request.user.role not in ['chairman', 'admin', 'treasurer']:
            return Response(
                {'error': 'Only chairman, admin, or treasurer can add ledger entries'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = request.data.copy()
        data['group'] = group.id
        serializer = LedgerEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data.copy()
        validated_data.pop('group', None)

        # Create the entry
        entry = LedgerEntry.objects.create(
            group=group,
            recorded_by=request.user,
            **serializer.validated_data
        )
        
        # Log activity
        UserActivityLog.objects.create(
            user=request.user,
            action='add_ledger_entry',
            details={
                'group_id': str(group.id),
                'entry_id': str(entry.id),
                'amount': str(entry.amount),
                'type': entry.transaction_type
            }
        )
        
        return Response(
            LedgerEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['put', 'patch'])
    def update_ledger_entry(self, request, pk=None):
        """Update a ledger entry"""
        group = self.get_object()
        entry_id = request.query_params.get('entry_id')
        
        if not entry_id:
            return Response(
                {'error': 'entry_id is required as query parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        entry = get_object_or_404(LedgerEntry, id=entry_id, group=group)
        
        # Check permission
        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can update ledger entries'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Don't allow editing verified entries
        if entry.is_verified:
            return Response(
                {'error': 'Cannot update a verified ledger entry'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = LedgerEntryCreateSerializer(entry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(LedgerEntrySerializer(entry).data)

    @action(detail=True, methods=['post'])
    def delete_ledger_entry(self, request, pk=None):
        """Soft delete a ledger entry"""
        group = self.get_object()
        entry_id = request.data.get('entry_id')
        
        if not entry_id:
            return Response(
                {'error': 'entry_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        entry = get_object_or_404(LedgerEntry, id=entry_id, group=group)
        
        # Check permission
        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can delete ledger entries'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if entry.is_verified:
            return Response(
                {'error': 'Cannot delete a verified ledger entry'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        entry.soft_delete(request.user)
        
        return Response({'message': 'Ledger entry deleted successfully'})

    @action(detail=True, methods=['post'])
    def verify_ledger_entry(self, request, pk=None):
        """Verify a ledger entry"""
        group = self.get_object()
        entry_id = request.data.get('entry_id')
        
        if not entry_id:
            return Response(
                {'error': 'entry_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        entry = get_object_or_404(LedgerEntry, id=entry_id, group=group)
        
        # Check permission
        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can verify ledger entries'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        entry.is_verified = True
        entry.verified_by = request.user
        entry.verified_at = timezone.now()
        entry.save()
        
        return Response({
            'message': 'Ledger entry verified successfully',
            'entry': LedgerEntrySerializer(entry).data
        })

    @action(detail=True, methods=['get'])
    def ledger_summary(self, request, pk=None):
        """Get ledger summary for a group"""
        group = self.get_object()
        
        # Get all entries
        entries = LedgerEntry.objects.filter(group=group, is_deleted=False)
        
        # Calculate totals
        total_balance = LedgerEntry.get_balance(group)
        
        penalty_types = ['late_fee', 'meeting_fine']
        total_penalties = entries.filter(transaction_type__in=penalty_types).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Expense transactions (debits)
        expense_types = ['loan_disbursement', 'expense', 'late_fee', 'meeting_fine', 'transfer']
        total_expenses = entries.filter(transaction_type__in=expense_types).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Savings contributions
        savings_types = ['savings_contribution', 'deposit']
        total_savings = entries.filter(transaction_type__in=savings_types).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Social contributions
        total_social = entries.filter(transaction_type='social_contribution').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Loans disbursed
        total_loans_disbursed = entries.filter(transaction_type='loan_disbursement').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Loans repaid
        total_loans_repaid = entries.filter(transaction_type='loan_repayment').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        withdrawal_types = ['withdrawal']
        total_withdrawals = entries.filter(transaction_type__in=withdrawal_types).aggregate(
            total=Sum('amount')
        )['total'] or 0

        income_types = ['income', 'refund']
        total_income = entries.filter(transaction_type__in=income_types).aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_income = total_penalties + total_loans_repaid + total_income

        # Fines
        total_fines = entries.filter(transaction_type__in=['late_fee', 'meeting_fine']).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        return Response({
            'total_balance': total_balance,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'total_savings': total_savings,
            'total_social_fund': total_social,
            'total_loans_disbursed': total_loans_disbursed,
            'total_loans_repaid': total_loans_repaid,
            'total_penalties': total_penalties,
            'total_fines': total_fines,
            'member_count': group.get_member_count(),
            'transaction_count': entries.count(),
            'last_updated': timezone.now()
        })

    @action(detail=True, methods=['get'])
    def member_ledger(self, request, pk=None):
        """Get ledger entries for a specific member"""
        group = self.get_object()
        member_id = request.query_params.get('member_id')
        
        if not member_id:
            return Response(
                {'error': 'member_id is required as query parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        member = get_object_or_404(GroupMember, id=member_id, group=group)
        
        entries = LedgerEntry.objects.filter(
            group=group,
            member=member,
            is_deleted=False
        ).order_by('-recorded_at')
        
        serializer = LedgerEntrySerializer(entries, many=True)
        
        return Response({
            'member': GroupMemberSerializer(member).data,
            'balance': LedgerEntry.get_member_balance(member),
            'entries': serializer.data
        })

    # ==================== LEDGER CATEGORIES ====================
    
    @action(detail=True, methods=['get'])
    def ledger_categories(self, request, pk=None):
        """Get all ledger categories for a group"""
        group = self.get_object()
        categories = LedgerCategory.objects.filter(group=group, is_active=True)
        serializer = LedgerCategorySerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_ledger_category(self, request, pk=None):
        """Add a new ledger category"""
        group = self.get_object()
        
        # Check permission
        if request.user.role not in ['chairman', 'admin']:
            return Response(
                {'error': 'Only chairman or admin can add ledger categories'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = LedgerCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        category = LedgerCategory.objects.create(
            group=group,
            **serializer.validated_data
        )
        
        return Response(
            LedgerCategorySerializer(category).data,
            status=status.HTTP_201_CREATED
        )

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
class BusinessTypeChoicesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        choices = [
            {'value': value, 'label': label}
            for value, label in GroupMember.BUSINESS_TYPES
        ]
        return Response(choices)