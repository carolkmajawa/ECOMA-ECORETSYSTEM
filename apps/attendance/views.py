from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta  
import logging
from decimal import Decimal
from apps.groups.models import Group, GroupMember
from .models import AttendanceCase, PenaltyPayment
from .models import Attendance, Meeting, ParticipationTracking
from .serializers import (
    AttendanceSerializer, AttendanceCreateSerializer,
    MeetingSerializer, MeetingCreateSerializer,
    ParticipationTrackingSerializer,  AttendanceCaseSerializer, AttendanceCaseCreateSerializer,
    PenaltyPaymentSerializer, PenaltyPaymentCreateSerializer
)
from apps.accounts.models import UserActivityLog

logger = logging.getLogger(__name__)

class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['meeting_date', 'meeting_type', 'attended', 'member', 'group']
    search_fields = ['member__full_name']
    ordering_fields = ['meeting_date', 'member__full_name']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Attendance.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return Attendance.objects.all()
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return Attendance.objects.filter(group__in=groups)
    
    def create(self, request):
        serializer = AttendanceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        member = serializer.validated_data['member']
        group = member.group
        
        attendance = Attendance.objects.create(
            group=group,
            recorded_by=request.user,
            **serializer.validated_data
        )
        
        UserActivityLog.objects.create(
            user=request.user,
            action='record_attendance',
            details={'attendance_id': str(attendance.id)}
        )
        
        return Response(AttendanceSerializer(attendance).data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple attendance records at once"""
        group_id = request.data.get('group_id')
        meeting_date = request.data.get('meeting_date')
        meeting_type = request.data.get('meeting_type', 'regular')
        attendees = request.data.get('attendees', [])
        
        if not group_id or not meeting_date:
            return Response(
                {'error': 'group_id and meeting_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group = get_object_or_404(Group, id=group_id)
        
        if request.user.role != 'admin' and request.user not in [group.chairman, group.secretary]:
            return Response(
                {'error': 'You do not have permission to record attendance for this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        created = []
        errors = []
        
        for member_id in attendees:
            try:
                member = GroupMember.objects.get(id=member_id, group=group)
                attendance, created_att = Attendance.objects.get_or_create(
                    member=member,
                    meeting_date=meeting_date,
                    defaults={
                        'group': group,
                        'meeting_type': meeting_type,
                        'attended': True,
                        'recorded_by': request.user
                    }
                )
                if created_att:
                    created.append(attendance.id)
            except GroupMember.DoesNotExist:
                errors.append(f'Member {member_id} not found in group')
        
        return Response({
            'message': f'Created {len(created)} attendance records',
            'created': created,
            'errors': errors
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get attendance statistics"""
        user = request.user
        if user.role == 'admin':
            groups = Group.objects.filter(is_active=True)
        else:
            groups = user.chairman_groups.all() | user.secretary_groups.all()
        
        if not groups:
            return Response({'error': 'No groups found'}, status=status.HTTP_400_BAD_REQUEST)
        
        attendances = Attendance.objects.filter(group__in=groups)
        total_attendances = attendances.count()
        attended = attendances.filter(attended=True).count()
        
        group_stats = []
        for group in groups:
            group_attendances = attendances.filter(group=group)
            group_total = group_attendances.count()
            group_attended = group_attendances.filter(attended=True).count()
            
            group_stats.append({
                'group_name': group.group_name,
                'total_meetings': group_total,
                'attended': group_attended,
                'attendance_rate': (group_attended / group_total * 100) if group_total > 0 else 0
            })
        
        return Response({
            'total_meetings': total_attendances,
            'attended': attended,
            'overall_attendance_rate': (attended / total_attendances * 100) if total_attendances > 0 else 0,
            'group_statistics': group_stats
        })
    
    @action(detail=False, methods=['get'], url_path='member/(?P<member_id>[^/.]+)')
    def member_attendance(self, request, member_id=None):
        """Get attendance history for a specific member"""
        member = get_object_or_404(GroupMember, id=member_id)
        attendances = self.get_queryset().filter(member=member).order_by('-meeting_date')
        
        total = attendances.count()
        attended = attendances.filter(attended=True).count()
        
        return Response({
            'member': {
                'id': str(member.id),
                'full_name': member.full_name,
                'group': member.group.group_name
            },
            'statistics': {
                'total_meetings': total,
                'attended': attended,
                'attendance_rate': (attended / total * 100) if total > 0 else 0
            },
            'history': AttendanceSerializer(attendances, many=True).data
        })

class MeetingViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['meeting_date', 'meeting_type', 'is_completed']
    search_fields = ['title', 'agenda']
    ordering_fields = ['meeting_date', 'title']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Meeting.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return Meeting.objects.all()
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return Meeting.objects.filter(group__in=groups)
    
    def create(self, request):
        group = request.user.chairman_groups.first()
        if not group:
            return Response(
                {'error': 'You must be a chairman to create meetings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MeetingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        meeting = Meeting.objects.create(
            group=group,
            created_by=request.user,
            **serializer.validated_data
        )
        
        return Response(MeetingSerializer(meeting).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        meeting = self.get_object()
        meeting.is_completed = True
        meeting.save()
        return Response({'message': 'Meeting marked as completed'})
    
    @action(detail=True, methods=['post'])
    def add_minutes(self, request, pk=None):
        meeting = self.get_object()
        minutes = request.data.get('minutes')
        if not minutes:
            return Response(
                {'error': 'Minutes are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        meeting.minutes = minutes
        meeting.save()
        
        return Response({'message': 'Minutes added successfully'})

class ParticipationTrackingViewSet(viewsets.ModelViewSet):
    serializer_class = ParticipationTrackingSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['member', 'meeting_date', 'participated']
    ordering_fields = ['meeting_date']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ParticipationTracking.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return ParticipationTracking.objects.all()
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return ParticipationTracking.objects.filter(member__group__in=groups)
    
    @action(detail=False, methods=['get'], url_path='member/(?P<member_id>[^/.]+)')
    def member_stats(self, request, member_id=None):
        """Get participation statistics for a member"""
        member = get_object_or_404(GroupMember, id=member_id)
        
        participations = self.get_queryset().filter(member=member)
        total = participations.count()
        participated = participations.filter(participated=True).count()
        total_points = participations.aggregate(total=sum('points'))['total'] or 0
        
        return Response({
            'member': {
                'id': str(member.id),
                'full_name': member.full_name
            },
            'statistics': {
                'total_events': total,
                'participated': participated,
                'participation_rate': (participated / total * 100) if total > 0 else 0,
                'total_points': total_points
            }
        })


class AttendanceCaseViewSet(viewsets.ModelViewSet):
    """
    📋 ViewSet for attendance cases and penalties
    """
    serializer_class = AttendanceCaseSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['case_type', 'status', 'member', 'meeting_date']
    search_fields = ['member__full_name', 'reason']
    ordering_fields = ['created_at', 'meeting_date']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AttendanceCase.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return AttendanceCase.objects.all()
        
        groups = user.chairman_groups.all() | user.secretary_groups.all()
        return AttendanceCase.objects.filter(group__in=groups)
    
    def create(self, request):
        """
        Create a new attendance case with penalty
        """
        serializer = AttendanceCaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        member = serializer.validated_data['member']
        group = member.group
        
        if request.user.role not in ['chairman', 'secretary', 'admin']:
            return Response(
                {'error': 'Only chairman, secretary, or admin can record cases'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        case = AttendanceCase.objects.create(
            group=group,
            recorded_by=request.user,
            **serializer.validated_data
        )
        
        UserActivityLog.objects.create(
            user=request.user,
            action='create_attendance_case',
            details={
                'case_id': str(case.id),
                'member': member.full_name,
                'case_type': case.case_type,
                'penalty': str(case.penalty_amount)
            }
        )
        
        return Response(AttendanceCaseSerializer(case).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_payment(self, request, pk=None):
        """
        💰 Add a penalty payment for a case
        """
        case = self.get_object()
        
        if case.status == 'resolved':
            return Response(
                {'error': 'This case is already resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        balance = case.get_penalty_balance()
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        amount = Decimal(str(amount))
        
        if amount > balance:
            return Response(
                {'error': f'Amount exceeds balance. Balance: MK{balance}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_serializer = PenaltyPaymentCreateSerializer(data=request.data)
        payment_serializer.is_valid(raise_exception=True)
        
        payment = PenaltyPayment.objects.create(
            group=case.group,
            member=case.member,
            attendance_case=case,
            recorded_by=request.user,
            **payment_serializer.validated_data
        )
        
        case.add_payment(amount)
        
        return Response(PenaltyPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        ✅ Resolve an attendance case
        """
        case = self.get_object()
        
        if case.status == 'resolved':
            return Response(
                {'error': 'Case is already resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not case.is_fully_paid() and case.penalty_amount > 0:
            balance = case.get_penalty_balance()
            return Response(
                {'error': f'Penalty not fully paid. Balance: MK{balance}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        case.status = 'resolved'
        case.resolved_by = request.user
        case.resolved_at = timezone.now()
        case.save()
        
        return Response({
            'message': 'Case resolved successfully',
            'case': AttendanceCaseSerializer(case).data
        })
    
    @action(detail=True, methods=['post'])
    def waive(self, request, pk=None):
        """
        🎯 Waive the penalty for a case
        """
        case = self.get_object()
        
        if case.status == 'resolved':
            return Response(
                {'error': 'Case is already resolved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        case.penalty_amount = 0
        case.penalty_paid = 0
        case.status = 'waived'
        case.resolved_by = request.user
        case.resolved_at = timezone.now()
        case.notes += f"\nPenalty waived by {request.user.get_full_name()}"
        case.save()
        
        return Response({
            'message': 'Penalty waived successfully',
            'case': AttendanceCaseSerializer(case).data
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        📊 Get summary of attendance cases
        """
        user = request.user
        
        if user.role == 'admin':
            groups = Group.objects.filter(is_active=True)
        else:
            groups = user.chairman_groups.all() | user.secretary_groups.all()
        
        if not groups:
            return Response({
                'total_cases': 0,
                'pending_cases': 0,
                'resolved_cases': 0,
                'total_penalties': 0,
                'total_paid': 0
            })
        
        cases = AttendanceCase.objects.filter(group__in=groups)
        
        total_cases = cases.count()
        pending_cases = cases.filter(status='pending').count()
        resolved_cases = cases.filter(status='resolved').count()
        waived_cases = cases.filter(status='waived').count()
        
        total_penalties = cases.aggregate(total=sum('penalty_amount'))['total'] or 0
        total_paid = cases.aggregate(total=sum('penalty_paid'))['total'] or 0
        
        case_types = {}
        for case_type, label in AttendanceCase.CASE_TYPES:
            count = cases.filter(case_type=case_type).count()
            if count > 0:
                case_types[label] = count
        
        return Response({
            'total_cases': total_cases,
            'pending_cases': pending_cases,
            'resolved_cases': resolved_cases,
            'waived_cases': waived_cases,
            'total_penalties': total_penalties,
            'total_paid': total_paid,
            'outstanding_balance': total_penalties - total_paid,
            'cases_by_type': case_types
        })
    
    @action(detail=False, methods=['get'], url_path='member/(?P<member_id>[^/.]+)')
    def member_cases(self, request, member_id=None):
        """
        👤 Get all cases for a specific member
        """
        member = get_object_or_404(GroupMember, id=member_id)
        cases = self.get_queryset().filter(member=member)
        
        total_penalty = cases.aggregate(total=sum('penalty_amount'))['total'] or 0
        total_paid = cases.aggregate(total=sum('penalty_paid'))['total'] or 0
        
        return Response({
            'member': {
                'id': str(member.id),
                'full_name': member.full_name,
                'phone_number': member.phone_number
            },
            'summary': {
                'total_cases': cases.count(),
                'pending_cases': cases.filter(status='pending').count(),
                'total_penalty': total_penalty,
                'total_paid': total_paid,
                'balance': total_penalty - total_paid
            },
            'cases': AttendanceCaseSerializer(cases, many=True).data
        })