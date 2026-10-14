from datetime import datetime
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.groups.models import Group, GroupMember, LedgerEntry
from apps.savings.models import Saving
from apps.loans.models import Loan
from apps.attendance.models import Attendance

User = get_user_model()

class ReportDataCollector:
    """Collect all data needed for a cycle report"""

    GENDER_LABELS = {'M': 'Male', 'F': 'Female', 'O': 'Other'}

    # Set to True to print only the last 4 characters of each national ID
    # (e.g. ****1234) in every report instead of the full number.
    MASK_NATIONAL_ID = False

    def __init__(self, group, start_date, end_date, include_members=None, include_sections=None):
        self.group = group
        self.start_date = start_date
        self.end_date = end_date
        self.include_members = include_members or []
        self.include_sections = include_sections or []
        self.member_ids = self.get_member_ids()
    
    def get_member_ids(self):
        """Get member IDs to include"""
        if self.include_members:
            return self.include_members
        return list(self.group.members.filter(is_active=True).values_list('id', flat=True))
    
    def collect_all(self):
        """Collect all report data"""
        data = {}
        
        sections = {
            'group_info': self.get_group_info,
            'cycle_info': self.get_cycle_info,
            'members': self.get_member_data,
            'contributions': self.get_contribution_summary,
            'loans': self.get_loan_summary,
            'transactions': self.get_transactions,
            'attendance': self.get_attendance_summary,
            'performance': self.get_member_performance,
            'financial_summary': self.get_financial_summary,
        }
        
        for section_id, section_func in sections.items():
            if not self.include_sections or section_id in self.include_sections:
                try:
                    data[section_id] = section_func()
                except Exception as e:
                    print(f"Error collecting {section_id}: {str(e)}")
                    data[section_id] = {'error': str(e)}
        
        data['metadata'] = {
            'generated_at': timezone.now().isoformat(),
            'generated_by': 'ECORET System',
            'version': '1.0',
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat(),
            }
        }
        
        return data
    
    def get_group_info(self):
        """Get group information, including the gender breakdown"""
        active = self.group.members.filter(is_active=True)
        total = active.count()
        male = active.filter(gender='M').count()
        female = active.filter(gender='F').count()
        other = active.filter(gender='O').count()

        return {
            'id': str(self.group.id),
            'name': self.group.group_name,
            'code': self.group.group_code,
            'address': self.group.address or 'N/A',
            'created_at': self.group.created_at.isoformat() if self.group.created_at else None,
            'is_active': self.group.is_active,
            'total_members': total,
            'active_members': total,
            'male_count': male,
            'female_count': female,
            'other_count': other,
            # members with no gender recorded (or an unexpected value)
            'unspecified_count': total - male - female - other,
        }
    
    def get_cycle_info(self):
        """Get cycle information from group fields"""
        return {
            'start_date': self.group.cycle_start_date.isoformat() if self.group.cycle_start_date else None,
            'end_date': self.group.cycle_end_date.isoformat() if self.group.cycle_end_date else None,
            'is_active': self.group.is_cycle_active,
            'duration_months': self.group.cycle_duration_months,
        }

    def _national_id(self, member):
        """National ID for display, optionally masked"""
        value = (member.national_id or '').strip()
        if not value:
            return 'N/A'
        if self.MASK_NATIONAL_ID and len(value) > 4:
            return '*' * (len(value) - 4) + value[-4:]
        return value
    
    def get_member_data(self):
        """Get member data"""
        members = self.group.members.filter(id__in=self.member_ids, is_active=True)
        return [{
            'id': str(m.id),
            'full_name': m.full_name,
            'national_id': self._national_id(m),
            'phone_number': m.phone_number,
            'gender': m.gender or 'N/A',
            'gender_label': self.GENDER_LABELS.get(m.gender, 'N/A'),
            'address': m.address or 'N/A',
            'joined_at': m.joined_date.isoformat() if m.joined_date else None,
            'is_active': m.is_active,
        } for m in members]
    
    def get_contribution_summary(self):
        """Get contribution summaries"""
        savings = Saving.objects.filter(
            group=self.group,
            member_id__in=self.member_ids,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        
        loans = Loan.objects.filter(
            group=self.group,
            member_id__in=self.member_ids,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        
        return {
            'total_savings': savings.aggregate(total=models.Sum('amount'))['total'] or 0,
            'total_loans': loans.aggregate(total=models.Sum('amount'))['total'] or 0,
            'savings_by_member': self.get_savings_by_member(savings),
            'loans_by_member': self.get_loans_by_member(loans),
        }
    
    def get_savings_by_member(self, savings):
        result = {}
        for saving in savings:
            member_id = str(saving.member_id)
            if member_id not in result:
                result[member_id] = {
                    'member_name': saving.member.full_name,
                    'total': 0,
                    'count': 0,
                }
            result[member_id]['total'] += saving.amount or 0
            result[member_id]['count'] += 1
        return result
    
    def get_loans_by_member(self, loans):
        result = {}
        for loan in loans:
            member_id = str(loan.member_id)
            if member_id not in result:
                result[member_id] = {
                    'member_name': loan.member.full_name,
                    'total': 0,
                    'count': 0,
                }
            result[member_id]['total'] += loan.amount or 0
            result[member_id]['count'] += 1
        return result
    
    def get_loan_summary(self):
        loans = Loan.objects.filter(
            group=self.group,
            member_id__in=self.member_ids,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        
        total_amount = loans.aggregate(total=models.Sum('amount'))['total'] or 0
        
        return {
            'total_loans': loans.count(),
            'total_amount': total_amount,
            'active_loans': loans.filter(status='active').count(),
            'approved_loans': loans.filter(status='approved').count(),
            'completed_loans': loans.filter(status='completed').count(),
            'defaulted_loans': loans.filter(status='defaulted').count(),
            'pending_loans': loans.filter(status='pending').count(),
        }
    
    def get_transactions(self):
        entries = LedgerEntry.objects.filter(
            group=self.group,
            is_deleted=False,
            recorded_at__gte=self.start_date,
            recorded_at__lte=self.end_date
        )
        
        if self.member_ids:
            entries = entries.filter(member_id__in=self.member_ids)
        
        total_amount = entries.aggregate(total=models.Sum('amount'))['total'] or 0
        
        return {
            'total_entries': entries.count(),
            'total_amount': total_amount,
            'transactions': [{
                'id': str(e.id),
                'date': e.recorded_at.isoformat() if e.recorded_at else None,
                # LedgerEntry has no `note` field, only `description`
                'description': e.description or 'N/A',
                'category': e.category or 'Uncategorized',
                'transaction_type': e.transaction_type,
                'amount': e.amount or 0,
                'member': e.member.full_name if e.member else None,
                'recorded_by': e.recorded_by.get_full_name() if e.recorded_by else 'System',
                'is_verified': e.is_verified,
            } for e in entries.order_by('-recorded_at')[:500]],
        }
    
    def get_attendance_summary(self):
        attendance = Attendance.objects.filter(
            member_id__in=self.member_ids,
            meeting_date__gte=self.start_date,
            meeting_date__lte=self.end_date
        )
        
        total_meetings = attendance.values('meeting_date').distinct().count()
        attended = attendance.filter(attended=True).count()
        not_attended = attendance.filter(attended=False).count()
        
        return {
            'total_meetings': total_meetings,
            'attended': attended,
            'not_attended': not_attended,
            'attendance_rate': (attended / (attended + not_attended) * 100) if (attended + not_attended) > 0 else 0,
            'by_member': self.get_attendance_by_member(attendance),
        }
    
    def get_attendance_by_member(self, attendance):
        result = {}
        for record in attendance:
            member_id = str(record.member_id)
            if member_id not in result:
                result[member_id] = {
                    'member_name': record.member.full_name,
                    'attended': 0,
                    'not_attended': 0,
                }
            if record.attended:
                result[member_id]['attended'] += 1
            else:
                result[member_id]['not_attended'] += 1
        return result
    
    def get_member_performance(self):
        members = self.group.members.filter(id__in=self.member_ids, is_active=True)
        performance = []
        
        for member in members:
            member_data = self.get_member_performance_data(member)
            performance.append(member_data)
        
        performance.sort(key=lambda x: x['total_contribution'], reverse=True)
        return performance
    
    def get_member_performance_data(self, member):
        savings = Saving.objects.filter(
            member=member,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        total_savings = savings.aggregate(total=models.Sum('amount'))['total'] or 0
        
        loans = Loan.objects.filter(
            member=member,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        total_loans = loans.aggregate(total=models.Sum('amount'))['total'] or 0
        
        attendance = Attendance.objects.filter(
            member=member,
            meeting_date__gte=self.start_date,
            meeting_date__lte=self.end_date
        )
        total_meetings = attendance.values('meeting_date').distinct().count()
        attended = attendance.filter(attended=True).count()
        
        rating = self.calculate_performance_rating(total_savings, total_loans, attended, total_meetings)
        
        return {
            'member_id': str(member.id),
            'full_name': member.full_name,
            'phone_number': member.phone_number,
            'total_savings': total_savings,
            'total_loans_taken': total_loans,
            'attendance_rate': (attended / total_meetings * 100) if total_meetings > 0 else 0,
            'meetings_attended': attended,
            'total_meetings': total_meetings,
            'total_contribution': total_savings + total_loans,
            'performance_rating': rating,
        }
    
    def calculate_performance_rating(self, total_savings, total_loans, attended, total_meetings):
        score = 0
        
        if total_savings > 0:
            score += min(40, (total_savings / 10000) * 10)
        
        if total_loans > 0:
            score += min(30, (total_loans / 5000) * 10)
        
        if total_meetings > 0:
            attendance_rate = (attended / total_meetings) * 100
            score += (attendance_rate / 100) * 30
        
        return min(100, score)
    
    def get_financial_summary(self):
        total_savings = Saving.objects.filter(
            group=self.group,
            member_id__in=self.member_ids,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        total_loans = Loan.objects.filter(
            group=self.group,
            member_id__in=self.member_ids,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        entries = LedgerEntry.objects.filter(
            group=self.group,
            is_deleted=False,
            recorded_at__gte=self.start_date,
            recorded_at__lte=self.end_date
        )
        if self.member_ids:
            entries = entries.filter(member_id__in=self.member_ids)
        
        total_amount = entries.aggregate(total=models.Sum('amount'))['total'] or 0
        
        return {
            'total_savings': total_savings,
            'total_loans_disbursed': total_loans,
            'total_contributions': total_savings + total_loans,
            'total_transactions': total_amount,
        }