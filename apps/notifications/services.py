# import logging
# from django.core.mail import send_mail
# from django.conf import settings
# from django.template.loader import render_to_string
# from django.utils import timezone
# from fcm_django.models import FCMDevice
# from firebase_admin.messaging import Message, Notification as FCMNotification
# from apps.accounts.models import UserDevice
# from apps.groups.models import GroupMember
# import africastalking

# logger = logging.getLogger(__name__)

# class NotificationService:
#     def __init__(self):
#         if settings.AFRICA_TALKING_USERNAME and settings.AFRICA_TALKING_API_KEY:
#             africastalking.initialize(
#                 settings.AFRICA_TALKING_USERNAME,
#                 settings.AFRICA_TALKING_API_KEY
#             )
#             self.sms = africastalking.SMS
#         else:
#             self.sms = None
    
#     def send_notification(self, user, title, message, notification_type='system', data=None):
#         """Send notification to a user"""
#         from .models import Notification
        
#         notification = Notification.objects.create(
#             user=user,
#             title=title,
#             message=message,
#             notification_type=notification_type,
#             data=data or {}
#         )
        
#         try:
#             prefs = user.notification_preferences
#         except:
#             from .models import NotificationPreference
#             prefs = NotificationPreference.objects.create(user=user)
        
#         if prefs.push_notifications:
#             self.send_push_notification(user, title, message, data)
        
#         if prefs.email_notifications:
#             self.send_email_notification(user, title, message)
        
#         if prefs.sms_notifications:
#             self.send_sms_notification(user, message)
        
#         return notification
    
#     def send_push_notification(self, user, title, message, data=None):
#         """Send push notification via FCM"""
#         try:
#             devices = UserDevice.objects.filter(user=user, is_active=True)
#             if not devices:
#                 return
            
#             fcm_devices = FCMDevice.objects.filter(
#                 registration_id__in=[d.fcm_token for d in devices],
#                 user=user
#             )
            
#             if not fcm_devices:
#                 return
            
#             for device in fcm_devices:
#                 device.send_message(
#                     Message(
#                         notification=FCMNotification(
#                             title=title,
#                             body=message
#                         ),
#                         data=data or {},
#                         android={
#                             'priority': 'high',
#                             'notification': {
#                                 'channel_id': 'ecoret_notifications'
#                             }
#                         },
#                         apns={
#                             'payload': {
#                                 'aps': {
#                                     'alert': {
#                                         'title': title,
#                                         'body': message
#                                     },
#                                     'sound': 'default'
#                                 }
#                             }
#                         }
#                     )
#                 )
#         except Exception as e:
#             logger.error(f'Failed to send push notification: {str(e)}')
    
#     def send_email_notification(self, user, title, message):
#         """Send email notification"""
#         try:
#             send_mail(
#                 title,
#                 message,
#                 settings.DEFAULT_FROM_EMAIL,
#                 [user.email],
#                 fail_silently=False
#             )
#         except Exception as e:
#             logger.error(f'Failed to send email notification: {str(e)}')
    
#     def send_sms_notification(self, user, message):
#         """Send SMS notification to a user via Africa's Talking"""
#         if not self.sms:
#             logger.warning("SMS service not configured")
#             return False
        
#         try:
#             response = self.sms.send(
#                 message,
#                 [user.phone_number],
#                 sender_id='ECORET' 
#             )
#             logger.info(f"SMS sent to {user.phone_number}: {response}")
#             return True
#         except Exception as e:
#             logger.error(f'Failed to send SMS to {user.phone_number}: {str(e)}')
#             return False
    
#     def send_direct_sms(self, phone_number, message):
#         """
#         Send SMS directly to a phone number without a user object.
#         Use this for members who don't have a user account yet.
#         """
#         if not self.sms:
#             logger.warning("SMS service not configured")
#             return False
        
#         try:
#             response = self.sms.send(
#                 message,
#                 [phone_number],
#                 sender_id='ECORET'
#             )
#             logger.info(f"Direct SMS sent to {phone_number}: {response}")
#             return True
#         except Exception as e:
#             logger.error(f'Failed to send direct SMS to {phone_number}: {str(e)}')
#             return False
    
#     def send_member_registration_sms(self, member, group):
#         """
#         Send SMS when a member is registered to a group
#         """
#         message = f"""
# ECORET: Welcome to {group.group_name}!
# Group Code: {group.group_code}
# Chairman: {group.chairman.get_full_name()}
# Dial *123# to access your group savings.
#         """
        
#         if member.user:
#             return self.send_sms_notification(member.user, message)
#         else:
#             return self.send_direct_sms(member.phone_number, message)
    
#     def send_member_removal_sms(self, member, group):
#         """
#         Send SMS when a member is removed from a group
#         """
#         message = f"""
# ECORET: You have been removed from {group.group_name}.
# Please contact your group chairman for more information.
#         """
        
#         if member.user:
#             return self.send_sms_notification(member.user, message)
#         else:
#             return self.send_direct_sms(member.phone_number, message)
   
#     def send_group_notification(self, group, title, message, notification_type='group_notice'):
#         """Send notification to all group members"""
#         from .models import Notification
        
#         members = GroupMember.objects.filter(group=group, is_active=True)
#         sent_count = 0
        
#         for member in members:
#             if member.user:
#                 self.send_notification(
#                     member.user,
#                     title,
#                     message,
#                     notification_type,
#                     {'group_id': str(group.id)}
#                 )
#                 sent_count += 1
        
#         return sent_count
    
#     def send_loan_approval_notification(self, loan):
#         """Send loan approval notification"""
#         user = loan.member.user
#         if user:
#             self.send_notification(
#                 user,
#                 'Loan Approved!',
#                 f'Your loan of MK{loan.amount} has been approved.',
#                 'loan_approval',
#                 {'loan_id': str(loan.id)}
#             )
        
#         for admin in [loan.group.chairman, loan.group.secretary]:
#             if admin:
#                 self.send_notification(
#                     admin,
#                     f'Loan Approved - {loan.member.full_name}',
#                     f'Loan of MK{loan.amount} has been approved for {loan.member.full_name}',
#                     'loan_approval',
#                     {'loan_id': str(loan.id)}
#                 )
    
#     def send_loan_due_reminder(self, loan):
#         """Send loan due reminder"""
#         user = loan.member.user
#         days_left = (loan.due_date - timezone.now()).days
        
#         if user:
#             self.send_notification(
#                 user,
#                 'Loan Due Reminder',
#                 f'Your loan of MK{loan.amount} is due in {days_left} days.',
#                 'loan_due',
#                 {'loan_id': str(loan.id), 'days_left': days_left}
#             )
        
#         for admin in [loan.group.chairman, loan.group.secretary]:
#             if admin:
#                 self.send_notification(
#                     admin,
#                     f'Loan Due - {loan.member.full_name}',
#                     f'Loan of MK{loan.amount} for {loan.member.full_name} is due in {days_left} days.',
#                     'loan_due',
#                     {'loan_id': str(loan.id), 'days_left': days_left}
#                 )
    
#     def send_new_loan_request_notification(self, loan_request):
#         """Send new loan request notification to ECORET admin"""
#         from django.contrib.auth import get_user_model
#         User = get_user_model()
        
#         admins = User.objects.filter(role='admin', is_active=True)
#         for admin in admins:
#             self.send_notification(
#                 admin,
#                 f'New Loan Request - {loan_request.group.group_name}',
#                 f'MK{loan_request.amount} loan request from {loan_request.group.group_name}',
#                 'loan_request',
#                 {'request_id': str(loan_request.id)}
#             )
    
#     def send_loan_request_approved_notification(self, loan_request):
#         """Send notification when loan request is approved"""
#         user = loan_request.requested_by
#         if user:
#             self.send_notification(
#                 user,
#                 'ECORET Loan Request Approved',
#                 f'Your loan request of MK{loan_request.amount} has been approved by ECORET.',
#                 'loan_approval',
#                 {'request_id': str(loan_request.id)}
#             )
    
#     def send_payment_received_notification(self, repayment):
#         """Send payment received notification"""
#         user = repayment.member.user
#         if user:
#             self.send_notification(
#                 user,
#                 'Payment Received',
#                 f'Your repayment of MK{repayment.amount} has been recorded.',
#                 'payment_received',
#                 {'repayment_id': str(repayment.id)}
#             )
    
#     def send_transaction_confirmation(self, user, transaction_type, amount, reference):
#         """
#         Send SMS confirmation for financial transactions
#         """
#         if transaction_type == 'loan_disbursement':
#             message = f"""
# ECORET: Your loan of MK{amount:,.2f} has been disbursed.
# Reference: {reference}
# Check your mobile money.
#             """
#         elif transaction_type == 'loan_repayment':
#             message = f"""
# ECORET: Your repayment of MK{amount:,.2f} has been received.
# Reference: {reference}
# Thank you!
#             """
#         elif transaction_type == 'savings_deposit':
#             message = f"""
# ECORET: Your savings of MK{amount:,.2f} has been recorded.
# Reference: {reference}
# Keep saving!
#             """
#         else:
#             message = f"""
# ECORET: Transaction of MK{amount:,.2f} completed.
# Reference: {reference}
#             """
        
#         return self.send_sms_notification(user, message)

# apps/notifications/services.py
import logging
from django.core.mail import send_mail
from django.conf import settings
from .models import Notification, NotificationQueue, NotificationPreference
from apps.accounts.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service class for sending notifications
    """
    
    def send_notification(self, user, title, message, notification_type='system', data=None):
        """
        Create a notification record for a user
        """
        try:
            notification = Notification.objects.create(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                data=data or {}
            )
            logger.info(f"Notification created for {user.email}: {title}")
            return notification
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    def send_email_notification(self, user, subject, message):
        """Send email notification to a user"""
        if not user:
            logger.warning("Cannot send email: User is None")
            return False
            
        try:
            # Check if user has email notifications enabled
            try:
                prefs = NotificationPreference.objects.get(user=user)
                if not prefs.email_notifications:
                    logger.info(f"📧 Email notifications disabled for {user.email}")
                    return False
            except NotificationPreference.DoesNotExist:
                pass
            
            if not user.email:
                logger.warning(f"❌ No email address for user {user.id}")
                return False
            
            # FIRST: Create notification record
            notification = self.send_notification(
                user=user,
                title=subject,
                message=message,
                notification_type='email'
            )
            
            if notification:
                # THEN: Send email
                send_mail(
                    subject=f'[ECORET] {subject}',
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                logger.info(f"✅ Email sent to {user.email}: {subject}")
                
                # THEN: Log to queue with the notification
                self.log_to_queue(
                    notification=notification,
                    channel='email',
                    status='sent'
                )
                return True
            else:
                logger.error(f"❌ Failed to create notification for {user.email}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to send email to {user.email}: {str(e)}")
            # Try to log failed queue item if notification exists
            if notification:
                self.log_to_queue(
                    notification=notification,
                    channel='email',
                    status='failed',
                    error=str(e)
                )
            return False
    
    def send_sms_notification(self, user, message):
        """
        Send SMS notification to a user
        """
        try:
            # Check if user has SMS notifications enabled
            try:
                prefs = NotificationPreference.objects.get(user=user)
                if not prefs.sms_notifications:
                    logger.info(f"SMS notifications disabled for {user.email}")
                    return False
            except NotificationPreference.DoesNotExist:
                pass
            
            if user and user.phone_number:
                return self.send_direct_sms(user.phone_number, message)
        except Exception as e:
            logger.error(f"Failed to send SMS to {user.phone_number}: {str(e)}")
            return False
    
    def send_direct_sms(self, phone_number, message):
        """
        Send SMS directly to a phone number
        """
        try:
            # Africa's Talking implementation
            from apps.ussd.services import AfricaTalkingService
            service = AfricaTalkingService()
            result = service.send_sms(phone_number, message)
            logger.info(f"SMS sent to {phone_number}")
            return result
        except Exception as e:
            logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
            return False
    
    def log_to_queue(self, notification, channel, status='pending', error=None):
        """
        Log notification to queue for tracking
        """
        if not notification:
            logger.warning("⚠️ Cannot log to queue: Notification is None")
            return None
        
        try:
            queue_item = NotificationQueue.objects.create(
                notification=notification,
                channel=channel,
                status=status,
                error_message=error or '',
                sent_at=timezone.now() if status == 'sent' else None
            )
            return queue_item
        except Exception as e:
            logger.error(f"Failed to log to queue: {str(e)}")
            return None
    
    def process_queue_item(self, queue_item):
        """
        Process a queue item and send the notification
        """
        try:
            notification = queue_item.notification
            user = notification.user
            
            if queue_item.channel == 'email':
                success = self.send_email_notification(user, notification.title, notification.message)
            elif queue_item.channel == 'sms':
                success = self.send_sms_notification(user, notification.message)
            else:
                success = False
            
            if success:
                queue_item.status = 'sent'
                queue_item.sent_at = timezone.now()
                queue_item.save()
                return True
            else:
                queue_item.status = 'failed'
                queue_item.attempt_count += 1
                queue_item.error_message = 'Failed to send'
                queue_item.save()
                return False
                
        except Exception as e:
            queue_item.status = 'failed'
            queue_item.attempt_count += 1
            queue_item.error_message = str(e)
            queue_item.save()
            return False
    
    def send_loan_approval_notification(self, loan):
        """
        Send loan approval notification
        """
        user = loan.member.user if loan.member.user else None
        if not user:
            return
        
        title = "Loan Approved"
        message = f"Your loan of MK{loan.amount:,.2f} has been approved."
        data = {'loan_id': str(loan.id), 'amount': str(loan.amount)}
        
        self.send_notification(user, title, message, 'loan_approval', data)
        self.send_email_notification(user, title, message)
    
    def send_new_loan_request_notification(self, loan_request):
        """
        Send notification for new loan request (to admin)
        """
        admins = User.objects.filter(role='admin')
        
        for admin in admins:
            title = "New Loan Request"
            message = f"A new loan request of MK{loan_request.amount:,.2f} has been submitted by {loan_request.requested_by.get_full_name()} for {loan_request.group.group_name}."
            data = {'request_id': str(loan_request.id)}
            self.send_notification(admin, title, message, 'loan_request', data)
            self.send_email_notification(admin, title, message)
    
    def send_loan_request_approved_notification(self, loan_request):
        """
        Send notification that loan request was approved
        """
        user = loan_request.requested_by
        title = "Loan Request Approved"
        message = f"Your loan request of MK{loan_request.amount:,.2f} for {loan_request.group.group_name} has been approved by ECORET Admin."
        data = {'request_id': str(loan_request.id)}
        
        self.send_notification(user, title, message, 'loan_approval', data)
        self.send_email_notification(user, title, message)
    
    def send_payment_received_notification(self, payment):
        """
        Send notification when a payment is received
        """
        user = payment.member.user if payment.member.user else None
        if not user:
            return
        
        title = "Payment Received"
        message = f"A payment of MK{payment.amount:,.2f} has been received for {payment.loan.member.full_name}."
        data = {'payment_id': str(payment.id), 'amount': str(payment.amount)}
        
        self.send_notification(user, title, message, 'payment_received', data)
        self.send_email_notification(user, title, message)
    
    def send_attendance_reminder(self, member, meeting):
        """
        Send attendance reminder to a member
        """
        user = member.user if member.user else None
        if not user:
            return
        
        title = "Attendance Reminder"
        message = f"Reminder: Meeting scheduled for {meeting.meeting_date.strftime('%Y-%m-%d')} at {meeting.meeting_time.strftime('%H:%M')}."
        data = {'meeting_id': str(meeting.id)}
        
        self.send_notification(user, title, message, 'attendance', data)
        self.send_sms_notification(user, message)