from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
import logging
from apps.groups.models import Group, GroupMember
from django.shortcuts import get_object_or_404

from .models import Saving, SavingGoal, SavingSummary
from .serializers import (
    SavingSerializer, SavingCreateSerializer,
    SavingGoalSerializer, SavingGoalCreateSerializer,
    SavingSummarySerializer
)
from apps.accounts.models import UserActivityLog

logger = logging.getLogger(__name__)

class SavingViewSet(viewsets.ModelViewSet):
    serializer_class = SavingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'saving_type', 'member', 'group']
    search_fields = ['member__full_name', 'reference_number']
    ordering_fields = ['transaction_date', 'amount']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view',False):
            return Saving.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return Saving.objects.all()
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return Saving.objects.filter(group__in=groups)
    
    def create(self, request):
        serializer = SavingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        member = serializer.validated_data['member']
        group = member.group
        
        # Check if group is active
        if not group.is_active:
            return Response(
                {'error': 'Group must be active to record savings'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        saving = Saving.objects.create(
            group=group,
            recorded_by=request.user,
            **serializer.validated_data
        )
        
        UserActivityLog.objects.create(
            user=request.user,
            action='record_saving',
            details={
                'saving_id': str(saving.id),
                'amount': str(saving.amount),
                'type': saving.transaction_type
            }
        )
        
        return Response(SavingSerializer(saving).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        user = request.user
        if user.role == 'admin':
            groups = Group.objects.filter(is_active=True)
        else:
            groups = user.chairman_groups.all() | user.secretary_groups.all()
        
        if not groups:
            return Response({'error': 'No groups found'}, status=status.HTTP_400_BAD_REQUEST)
        
        total_savings = Saving.objects.filter(group__in=groups).aggregate(
            total_deposits=Sum('amount', filter=Q(transaction_type='deposit')),
            total_withdrawals=Sum('amount', filter=Q(transaction_type='withdrawal'))
        )
        
        total_deposits = total_savings['total_deposits'] or 0
        total_withdrawals = total_savings['total_withdrawals'] or 0
        balance = total_deposits - total_withdrawals
        
        return Response({
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'balance': balance,
            'group_count': groups.count()
        })
    
    @action(detail=True, methods=['get'], url_path='member/(?P<member_id>[^/.]+)')
    def member_savings(self, request, member_id=None):
        member = get_object_or_404(GroupMember, id=member_id)
        savings = self.get_queryset().filter(member=member)
        
        total_deposits = savings.filter(transaction_type='deposit').aggregate(total=Sum('amount'))['total'] or 0
        total_withdrawals = savings.filter(transaction_type='withdrawal').aggregate(total=Sum('amount'))['total'] or 0
        
        return Response({
            'member': {
                'id': str(member.id),
                'full_name': member.full_name,
                'phone_number': member.phone_number
            },
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'balance': total_deposits - total_withdrawals,
            'transactions': SavingSerializer(savings, many=True).data
        })

class SavingGoalViewSet(viewsets.ModelViewSet):
    serializer_class = SavingGoalSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_completed']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SavingGoal.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return SavingGoal.objects.all()
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return SavingGoal.objects.filter(group__in=groups)
    
    def create(self, request):
        # Get user's group
        group = request.user.chairman_groups.first()
        if not group:
            return Response(
                {'error': 'You must be a chairman to create saving goals'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = SavingGoalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        goal = SavingGoal.objects.create(
            group=group,
            **serializer.validated_data
        )
        
        return Response(SavingGoalSerializer(goal).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_funds(self, request, pk=None):
        goal = self.get_object()
        
        amount = request.data.get('amount')
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = float(amount)
        except ValueError:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount <= 0:
            return Response(
                {'error': 'Amount must be greater than 0'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        goal.current_amount += amount
        if goal.current_amount >= goal.target_amount:
            goal.is_completed = True
        goal.save()
        
        return Response(SavingGoalSerializer(goal).data)