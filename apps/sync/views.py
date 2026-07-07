from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
import logging

from .serializers import DeviceSyncSerializer
from apps.groups.models import Group, GroupMember
from apps.loans.models import Loan, LoanRepayment

try:
    from apps.shares.models import Share
except ImportError:
    Share = None
    logger.warning("Shares app not found. Share sync disabled.")

from apps.attendance.models import Attendance, AttendanceCase
from .models import DeviceSync, SyncLog

logger = logging.getLogger(__name__)


class SyncView(APIView):
    """
    📱 Sync data between mobile app and server
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        📥 Download data for offline use
        """
        user = request.user
        device_id = request.query_params.get('device_id')
        
        if not device_id:
            return Response(
                {'error': 'device_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            device, created = DeviceSync.objects.get_or_create(
                user=user,
                device_id=device_id,
                defaults={
                    'device_name': request.query_params.get('device_name', '')
                }
            )
            
            if user.role == 'admin':
                groups = Group.objects.filter(is_active=True)
            else:
                groups = user.chairman_groups.all() | user.secretary_groups.all()
            
            response_data = {
                'groups': [],
                'members': [],
                'loans': [],
                'repayments': [],
                'savings': [],
                'attendance': [],
                'attendance_cases': [],
                'timestamp': timezone.now().isoformat()
            }
            
            for group in groups:
                response_data['groups'].append({
                    'id': str(group.id),
                    'group_name': group.group_name,
                    'group_code': group.group_code,
                    'is_active': group.is_active,
                    'default_interest_rate': str(group.default_interest_rate),
                    'cycle_start_date': group.cycle_start_date.isoformat() if group.cycle_start_date else None,
                    'cycle_end_date': group.cycle_end_date.isoformat() if group.cycle_end_date else None,
                    'is_cycle_active': group.is_cycle_active,
                    'created_at': group.created_at.isoformat(),
                    'updated_at': group.updated_at.isoformat()
                })
                
                for member in group.members.filter(is_active=True):
                    response_data['members'].append({
                        'id': str(member.id),
                        'group_id': str(member.group.id),
                        'full_name': member.full_name,
                        'phone_number': member.phone_number,
                        'business_type': member.business_type,
                        'is_active': member.is_active,
                        'joined_date': member.joined_date.isoformat(),
                        'updated_at': member.updated_at.isoformat()
                    })
                
                for loan in group.loans.filter(status__in=['active', 'approved']):
                    response_data['loans'].append({
                        'id': str(loan.id),
                        'member_id': str(loan.member.id),
                        'amount': str(loan.amount),
                        'interest_rate': str(loan.interest_rate),
                        'total_payable': str(loan.total_payable),
                        'duration_months': loan.duration_months,
                        'status': loan.status,
                        'due_date': loan.due_date.isoformat() if loan.due_date else None,
                        'created_at': loan.created_at.isoformat()
                    })
                
                for repayment in LoanRepayment.objects.filter(loan__group=group):
                    response_data['repayments'].append({
                        'id': str(repayment.id),
                        'loan_id': str(repayment.loan.id),
                        'member_id': str(repayment.member.id),
                        'amount': str(repayment.amount),
                        'principal_paid': str(repayment.principal_paid),
                        'interest_paid': str(repayment.interest_paid),
                        'payment_date': repayment.payment_date.isoformat(),
                        'payment_method': repayment.payment_method
                    })
                
                if Share is not None:
                    for share in Share.objects.filter(group=group):
                        response_data['shares'].append({
                            'id': str(share.id),
                            'member_id': str(share.member.id),
                            'amount': str(share.amount),
                            'transaction_type': share.transaction_type,
                            'transaction_date': share.transaction_date.isoformat()
                        })
                
                for attendance in Attendance.objects.filter(group=group):
                    response_data['attendance'].append({
                        'id': str(attendance.id),
                        'member_id': str(attendance.member.id),
                        'meeting_date': attendance.meeting_date.isoformat(),
                        'attended': attendance.attended,
                        'meeting_type': attendance.meeting_type,
                        'time_in': attendance.time_in.isoformat() if attendance.time_in else None,
                        'time_out': attendance.time_out.isoformat() if attendance.time_out else None
                    })
                
                for case in AttendanceCase.objects.filter(group=group):
                    response_data['attendance_cases'].append({
                        'id': str(case.id),
                        'member_id': str(case.member.id),
                        'case_type': case.case_type,
                        'penalty_amount': str(case.penalty_amount),
                        'penalty_paid': str(case.penalty_paid),
                        'status': case.status,
                        'meeting_date': case.meeting_date.isoformat(),
                        'reason': case.reason,
                        'penalty_due_date': case.penalty_due_date.isoformat() if case.penalty_due_date else None
                    })
            
            device.last_sync_at = timezone.now()
            device.total_syncs += 1
            device.save()
            
            SyncLog.objects.create(
                user=user,
                device=device,
                action='download',
                entity_type='all',
                status='success',
                data_received={'groups_count': len(groups)}
            )
            
            return Response({
                'success': True,
                'data': response_data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Sync download error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """
        📤 Upload offline changes from mobile app
        """
        user = request.user
        data = request.data
        device_id = request.data.get('device_id')
        
        if not device_id:
            return Response(
                {'error': 'device_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            device = DeviceSync.objects.get(user=user, device_id=device_id)
            
            results = {
                'created': [],
                'updated': [],
                'errors': []
            }
            
            entity_handlers = {
                'members': self.process_member_sync,
                'attendance': self.process_attendance_sync,
                'attendance_cases': self.process_attendance_case_sync,
                'loans': self.process_loan_sync,
                'repayments': self.process_repayment_sync,
                'share': self.process_share_sync if Share is not None else None,
            }
            
            for entity_type, handler in entity_handlers.items():
                if handler and entity_type in data:
                    result = handler(user, data[entity_type])
                    results['created'].extend(result['created'])
                    results['updated'].extend(result['updated'])
                    results['errors'].extend(result['errors'])
            
            device.last_sync_at = timezone.now()
            device.total_syncs += 1
            device.save()
            
            SyncLog.objects.create(
                user=user,
                device=device,
                action='upload',
                entity_type='all',
                status='success' if not results['errors'] else 'partial',
                data_sent={'processed': len(data)},
                error_message=str(results['errors']) if results['errors'] else ''
            )
            
            return Response({
                'success': True,
                'results': results,
                'timestamp': timezone.now().isoformat()
            })
            
        except DeviceSync.DoesNotExist:
            return Response(
                {'error': 'Device not found. Please sync first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Sync upload error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def process_member_sync(self, user, members):
        """Process member data from offline"""
        results = {'created': [], 'updated': [], 'errors': []}
        
        for member_data in members:
            try:
                member = GroupMember.objects.filter(
                    id=member_data.get('id')
                ).first()
                if member_data.get('group_id'):
                    group = Group.objects.filter(
                        Q(chairman=user) | Q(secretary=user),
                        id=member_data['group_id']
                    ).first()
                    if not group:
                        results['errors'].append({
                            'id': member_data.get('id'),
                            'error': 'Group not accessible'
                        })
                        continue
                
                if member:
                    for key, value in member_data.items():
                        if key in ['id', 'group_id']:
                            continue
                        setattr(member, key, value)
                    member.save()
                    results['updated'].append(str(member.id))
                else:
                    member = GroupMember.objects.create(
                        **member_data
                    )
                    results['created'].append(str(member.id))
                    
            except Exception as e:
                results['errors'].append({
                    'id': member_data.get('id'),
                    'error': str(e)
                })
        
        return results

    def process_attendance_sync(self, user, attendance_records):
        """Process attendance data from offline"""
        results = {'created': [], 'updated': [], 'errors': []}
        
        for att_data in attendance_records:
            try:
                attendance = Attendance.objects.filter(
                    id=att_data.get('id')
                ).first()
                
                if attendance:
                    attendance.attended = att_data.get('attended', attendance.attended)
                    attendance.save()
                    results['updated'].append(str(attendance.id))
                else:
                    attendance = Attendance.objects.create(
                        **att_data
                    )
                    results['created'].append(str(attendance.id))
                    
            except Exception as e:
                results['errors'].append({
                    'id': att_data.get('id'),
                    'error': str(e)
                })
        
        return results

    def process_attendance_case_sync(self, user, cases):
        """Process attendance cases from offline"""
        results = {'created': [], 'updated': [], 'errors': []}
        
        for case_data in cases:
            try:
                case = AttendanceCase.objects.filter(
                    id=case_data.get('id')
                ).first()
                
                if case:
                    case.status = case_data.get('status', case.status)
                    case.notes = case_data.get('notes', case.notes)
                    case.save()
                    results['updated'].append(str(case.id))
                else:
                    case = AttendanceCase.objects.create(
                        **case_data
                    )
                    results['created'].append(str(case.id))
                    
            except Exception as e:
                results['errors'].append({
                    'id': case_data.get('id'),
                    'error': str(e)
                })
        
        return results

    def process_loan_sync(self, user, loans):
        """Process loan data from offline"""
        results = {'created': [], 'updated': [], 'errors': []}
        
        for loan_data in loans:
            try:
                loan = Loan.objects.filter(
                    id=loan_data.get('id')
                ).first()
                
                if loan:
                    loan.status = loan_data.get('status', loan.status)
                    loan.save()
                    results['updated'].append(str(loan.id))
                else:
                    loan = Loan.objects.create(
                        **loan_data,
                        status='pending'
                    )
                    results['created'].append(str(loan.id))
                    
            except Exception as e:
                results['errors'].append({
                    'id': loan_data.get('id'),
                    'error': str(e)
                })
        
        return results

    def process_repayment_sync(self, user, repayments):
        """Process repayment data from offline"""
        results = {'created': [], 'updated': [], 'errors': []}
        
        for repayment_data in repayments:
            try:
                repayment = LoanRepayment.objects.filter(
                    id=repayment_data.get('id')
                ).first()
                
                if repayment:
                    results['updated'].append(str(repayment.id))
                else:
                    repayment = LoanRepayment.objects.create(
                        **repayment_data
                    )
                    results['created'].append(str(repayment.id))
                    
            except Exception as e:
                results['errors'].append({
                    'id': repayment_data.get('id'),
                    'error': str(e)
                })
        
        return results

    def process_share_sync(self, user, shares):
        """Process share data from offline"""
        results = {'created': [], 'updated': [], 'errors': []}
        
        if Share is None:
            results['errors'].append({
                'id': 'all',
                'error': 'Shares app not available'
            })
            return results
        
        for share_data in shares:
            try:
                share = Share.objects.filter(
                    id=share_data.get('id')
                ).first()
                
                if share:
                    results['updated'].append(str(share.id))
                else:
                    share = Share.objects.create(
                        **share_data
                    )
                    results['created'].append(str(share.id))
                    
            except Exception as e:
                results['errors'].append({
                    'id': share_data.get('id'),
                    'error': str(e)
                })
        
        return results


class SyncStatusView(APIView):
    """
    📊 Get sync status for a device
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        device_id = request.query_params.get('device_id')
        
        if not device_id:
            return Response(
                {'error': 'device_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            device = DeviceSync.objects.get(user=user, device_id=device_id)
            serializer = DeviceSyncSerializer(device)
            return Response(serializer.data)
        except DeviceSync.DoesNotExist:
            return Response({
                'user': str(user.id),
                'device_id': device_id,
                'last_sync_at': None,
                'total_syncs': 0,
                'synced': False
            })