# from rest_framework import viewsets, status, permissions, filters
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from django_filters.rest_framework import DjangoFilterBackend
# from django.shortcuts import get_object_or_404
# import logging
# from django.utils import timezone

# from .models import Notification, NotificationPreference
# from .serializers import (
#     NotificationSerializer, NotificationPreferenceSerializer
# )
# from .services import NotificationService

# logger = logging.getLogger(__name__)

# class NotificationViewSet(viewsets.ModelViewSet):
#     serializer_class = NotificationSerializer
#     filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
#     filterset_fields = ['is_read', 'notification_type']
#     search_fields = ['title', 'message']
#     ordering_fields = ['created_at']
    
#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return Notification.objects.none()
        
#         return Notification.objects.filter(user=self.request.user)
    
#     @action(detail=True, methods=['post'])
#     def mark_read(self, request, pk=None):
#         notification = self.get_object()
#         notification.mark_as_read()
#         return Response({'message': 'Notification marked as read'})
    
#     @action(detail=False, methods=['post'])
#     def mark_all_read(self, request):
#         self.get_queryset().filter(is_read=False).update(
#             is_read=True,
#             read_at=timezone.now()
#         )
#         return Response({'message': 'All notifications marked as read'})
    
#     @action(detail=False, methods=['get'])
#     def unread_count(self, request):
#         count = self.get_queryset().filter(is_read=False).count()
#         return Response({'unread_count': count})

# class NotificationPreferenceViewSet(viewsets.ModelViewSet):
#     serializer_class = NotificationPreferenceSerializer
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return NotificationPreference.objects.none()
        
#         return NotificationPreference.objects.filter(user=self.request.user)
    
#     def create(self, request):
#         if NotificationPreference.objects.filter(user=request.user).exists():
#             return Response(
#                 {'error': 'Preferences already exist for this user'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         serializer = NotificationPreferenceSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         preferences = NotificationPreference.objects.create(
#             user=request.user,
#             **serializer.validated_data
#         )
        
#         return Response(NotificationPreferenceSerializer(preferences).data, 
#                        status=status.HTTP_201_CREATED)
    
    
# apps/notifications/views.py
from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
import logging
from django.utils import timezone
from rest_framework.permissions import AllowAny

from .models import Notification, NotificationPreference, NotificationQueue
from .serializers import (
    NotificationSerializer, NotificationPreferenceSerializer, NotificationQueueSerializer
)
from .services import NotificationService
from apps.accounts.models import UserActivityLog
from apps.groups.models import Group

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_read', 'notification_type', 'group']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return Notification.objects.all()
        return Notification.objects.filter(user=user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'message': 'Notification marked as read'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'message': 'All notifications marked as read'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Get latest 10 notifications"""
        notifications = self.get_queryset()[:10]
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return NotificationPreference.objects.none()
        
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def create(self, request):
        if NotificationPreference.objects.filter(user=request.user).exists():
            return Response(
                {'error': 'Preferences already exist for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = NotificationPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        preferences = NotificationPreference.objects.create(
            user=request.user,
            **serializer.validated_data
        )
        
        return Response(NotificationPreferenceSerializer(preferences).data, 
                       status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        preferences = self.get_object()
        serializer = NotificationPreferenceSerializer(preferences, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class NotificationQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing notification queue (admin only)
    """
    serializer_class = NotificationQueueSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return NotificationQueue.objects.none()
        
        user = self.request.user
        if user.role == 'admin':
            return NotificationQueue.objects.all()
        return NotificationQueue.objects.filter(notification__user=user)
    
    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed notification"""
        queue_item = self.get_object()
        if queue_item.status != 'failed':
            return Response(
                {'error': 'Only failed notifications can be retried'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset and retry
        queue_item.status = 'pending'
        queue_item.attempt_count = 0
        queue_item.error_message = ''
        queue_item.save()
        
        # Process the notification
        service = NotificationService()
        success = service.process_queue_item(queue_item)
        
        if success:
            return Response({'message': 'Notification retried successfully'})
        else:
            return Response(
                {'error': 'Failed to send notification'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SendNotificationView(APIView):
    """
    API View to send notifications to group members
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        group_id = request.data.get('group_id')
        subject = request.data.get('subject')
        message = request.data.get('message')
        notification_type = request.data.get('notification_type', 'email')
        notification_category = request.data.get('category', 'group_notice')
        
        # Validate input
        if not group_id:
            return Response(
                {'error': 'group_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not subject:
            return Response(
                {'error': 'subject is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not message:
            return Response(
                {'error': 'message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if group exists and user has permission
        group = get_object_or_404(Group, id=group_id)
        user = request.user
        
        if user.role != 'admin' and user != group.chairman:
            return Response(
                {'error': 'You do not have permission to send notifications to this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            service = NotificationService()
            
            # Send to all active members
            sent_count = 0
            failed_count = 0
            
            for member in group.members.filter(is_active=True):
                try:
                    member_user = member.user
                    
                    if member_user:
                        # Create notification record
                        notification = service.send_notification(
                            user=member_user,
                            title=subject,
                            message=message,
                            notification_type=notification_category,
                            data={
                                'group_id': str(group.id),
                                'group_name': group.group_name,
                                'sent_by': user.get_full_name() or user.email
                            }
                        )
                        
                        # Send via email if enabled
                        if notification_type in ['email', 'both']:
                            service.send_email_notification(member_user, subject, message)
                        
                        # Send via SMS if enabled
                        if notification_type in ['sms', 'both']:
                            if member.phone_number:
                                service.send_direct_sms(
                                    member.phone_number,
                                    f"ECORET: {subject}\n\n{message}"
                                )
                        
                        sent_count += 1
                    else:
                        # User doesn't have account, send SMS directly
                        if member.phone_number and notification_type in ['sms', 'both']:
                            service.send_direct_sms(
                                member.phone_number,
                                f"ECORET: {subject}\n\n{message}\n\nGroup: {group.group_name}"
                            )
                            sent_count += 1
                        else:
                            failed_count += 1
                            
                except Exception as e:
                    logger.error(f"Failed to notify {member.full_name}: {str(e)}")
                    failed_count += 1
            
            # Log activity
            UserActivityLog.objects.create(
                user=request.user,
                action='send_group_notification',
                details={
                    'group_id': str(group.id), 
                    'group_name': group.group_name,
                    'title': subject, 
                    'sent_count': sent_count,
                    'failed_count': failed_count,
                    'notification_type': notification_type
                }
            )
            
            return Response({
                'message': f'Notification sent to {sent_count} member(s)',
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_members': group.members.filter(is_active=True).count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            return Response(
                {'error': f'Failed to send notification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class TestNotificationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        return Response({
            'message': 'POST request successful!',
            'data': request.data
        }, status=status.HTTP_200_OK)
    
    def get(self, request):
        return Response({
            'message': 'GET request successful!'
        }, status=status.HTTP_200_OK)        