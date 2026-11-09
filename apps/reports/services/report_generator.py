from datetime import datetime, date, time
from django.db.models import Q, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.groups.models import Group, GroupMember, LedgerEntry
from apps.savings.models import Saving
from apps.loans.models import Loan
from apps.attendance.models import Attendance

User = get_user_model()

# Same rule LedgerEntry.save() uses for the running balance:
# these add to the balance, everything else subtracts.
CREDIT_TYPES = [
    'savings_contribution', 'social_contribution', 'loan_repayment',
    'loan_interest', 'income', 'refund', 'deposit',
]
PENALTY_TYPES = ['late_fee', 'meeting_fine']


def _f(value):
    """Decimal / None -> float, so the report data is always JSON-safe."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _total(queryset):
    return _f(queryset.aggregate(total=Sum('amount'))['total'])


class ReportDataCollector:
    """Collect all data needed for a cycle report"""

    GENDER_LABELS = {'M': 'Male', 'F': 'Female', 'O': 'Other'}

    # Set to True to print only the last 4 characters of each national ID
    # (e.g. ****1234) in every report instead of the full number.
    MASK_NATIONAL_ID = False

    def __init__(self, group, start_date, end_date, include_members=None, include_sections=None):
        self.group = group
        self.start_date, self.end_date = self._normalize_range(start_date, end_date)
        self.include_members = include_members or []
        self.include_sections = include_sections or []
        self.member_ids = self.get_member_ids()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _as_dt(value, end=False):
        """Accept a date or a datetime and always return a datetime."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return timezone.make_aware(datetime.combine(value, time.max if end else time.min))
        return value

    def _normalize_range(self, start, end):
        start, end = self._as_dt(start), self._as_dt(end, end=True)
        if isinstance(start, datetime) and isinstance(end, datetime):
            local_start = timezone.localtime(start) if timezone.is_aware(start) else start
            local_end = timezone.localtime(end) if timezone.is_aware(end) else end
            # A "range" that starts and ends on the same day means the whole day
            if local_start.date() == local_end.date():
                start = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
                end = local_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end

    def _ledger_qs(self):
        """Ledger entries in the report period (whole group unless members were picked)."""
        qs = LedgerEntry.objects.filter(
            group=self.group,
            is_deleted=False,
            recorded_at__gte=self.start_date,
            recorded_at__lte=self.end_date,
        )
        if self.include_members:
            qs = qs.filter(member_id__in=self.include_members)
        return qs

    def _savings_qs(self):
        qs = Saving.objects.filter(
            group=self.group,
            transaction_date__gte=self.start_date,
            transaction_date__lte=self.end_date,
        )
        if self.include_members:
            qs = qs.filter(member_id__in=self.include_members)
        return qs

    def _loans_qs(self):
        qs = Loan.objects.filter(
            group=self.group,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date,
        )
        if self.include_members:
            qs = qs.filter(member_id__in=self.include_members)
        return qs

    def _is_disbursed(self, loan):
        """Money has actually been paid out (an 'approved' loan may still be waiting)."""
        status = getattr(loan, 'disbursement_status', None)
        if status is not None:
            return status == 'completed'
        return loan.status in ('active', 'completed', 'defaulted')

    def _loan_payable(self, loan):
        return _f(getattr(loan, 'total_payable', None)) or _f(loan.amount)

    def _loan_paid(self, loan):
        paid = getattr(loan, 'total_paid', None)
        if callable(paid):
            paid = paid()
        if paid is None:
            paid = LedgerEntry.objects.filter(
                group=self.group, is_deleted=False,
                transaction_type='loan_repayment', loan=loan,
            ).aggregate(total=Sum('amount'))['total']
        return _f(paid)

    def get_member_ids(self):
        """Get member IDs to include"""
        if self.include_members:
            return self.include_members
        return list(self.group.members.filter(is_active=True).values_list('id', flat=True))

    # ---------------------------------------------------------------- main entry
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

    # ------------------------------------------------------------------ sections
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

    def _savings_balance(self):
        """Net savings of the whole group to date (not limited to the report period)"""
        all_savings = Saving.objects.filter(group=self.group)
        return (
            _total(all_savings.filter(transaction_type='deposit'))
            - _total(all_savings.filter(transaction_type='withdrawal'))
        )

    def get_contribution_summary(self):
        """Savings, social fund, penalties and interest for the period"""
        savings = self._savings_qs()
        ledger = self._ledger_qs()
        loans = self._loans_qs().select_related('member')

        deposits = _total(savings.filter(transaction_type='deposit'))
        withdrawals = _total(savings.filter(transaction_type='withdrawal'))

        return {
            'total_savings': deposits,                      # deposits in the period
            'total_withdrawals': withdrawals,
            'net_savings': deposits - withdrawals,
            'savings_balance': self._savings_balance(),    # to date
            'total_social': _total(ledger.filter(transaction_type='social_contribution')),
            'total_penalties': _total(ledger.filter(transaction_type__in=PENALTY_TYPES)),
            'total_interest': _total(ledger.filter(transaction_type='loan_interest')),
            'total_loans': _total(loans),                   # principal requested in the period
            'savings_by_member': self.get_savings_by_member(savings),
            'loans_by_member': self.get_loans_by_member(loans),
        }

    def get_savings_by_member(self, savings):
        result = {}
        for saving in savings.select_related('member'):
            member_id = str(saving.member_id)
            entry = result.setdefault(member_id, {
                'member_name': saving.member.full_name,
                'total': 0.0,
                'count': 0,
            })
            amount = _f(saving.amount)
            entry['total'] += amount if saving.transaction_type == 'deposit' else -amount
            entry['count'] += 1
        return result

    def get_loans_by_member(self, loans):
        result = {}
        for loan in loans:
            member_id = str(loan.member_id)
            entry = result.setdefault(member_id, {
                'member_name': loan.member.full_name,
                'total': 0.0,
                'count': 0,
            })
            entry['total'] += _f(loan.amount)
            entry['count'] += 1
        return result

    def get_loan_summary(self):
        """Loans requested in the period, with what has been repaid on them"""
        loans = list(self._loans_qs().select_related('member'))
        disbursed = [loan for loan in loans if self._is_disbursed(loan)]

        total_disbursed = sum(_f(loan.amount) for loan in disbursed)
        total_payable = 0.0
        total_repaid = 0.0
        total_balance = 0.0
        for loan in disbursed:
            payable = self._loan_payable(loan)
            paid = self._loan_paid(loan)
            total_payable += payable
            total_repaid += paid
            total_balance += max(payable - paid, 0.0)

        loan_rows = []
        for loan in loans:
            payable = self._loan_payable(loan)
            paid = self._loan_paid(loan) if self._is_disbursed(loan) else 0.0
            loan_rows.append({
                'member': loan.member.full_name if loan.member else 'N/A',
                'amount': _f(loan.amount),
                'interest_rate': _f(getattr(loan, 'interest_rate', 0)),
                'total_payable': payable,
                'paid': paid,
                'balance': max(payable - paid, 0.0) if self._is_disbursed(loan) else 0.0,
                'status': loan.status,
                'disbursement_status': getattr(loan, 'disbursement_status', '') or '',
                'requested_on': loan.created_at.date().isoformat() if loan.created_at else '',
            })

        def count(status):
            return sum(1 for loan in loans if loan.status == status)

        return {
            'total_loans': len(loans),
            'total_amount': sum(_f(loan.amount) for loan in loans),
            'total_disbursed': total_disbursed,
            'total_repaid': total_repaid,
            'total_balance': total_balance,
            'repayment_rate': (total_repaid / total_payable * 100) if total_payable else 0.0,
            'active_loans': count('active'),
            'approved_loans': count('approved'),
            'completed_loans': count('completed'),
            'defaulted_loans': count('defaulted'),
            'pending_loans': count('pending'),
            'loans': loan_rows,
        }

    def get_transactions(self):
        """Ledger totals for the period (credits add to the balance, debits subtract)"""
        entries = self._ledger_qs()
        total_credit = _total(entries.filter(transaction_type__in=CREDIT_TYPES))
        total_debit = _total(entries.exclude(transaction_type__in=CREDIT_TYPES))
        rows = entries.select_related('member', 'recorded_by').order_by('-recorded_at')[:500]

        return {
            'total_entries': entries.count(),
            'total_credit': total_credit,
            'total_debit': total_debit,
            'net_balance': total_credit - total_debit,
            'total_amount': total_credit + total_debit,
            'transactions': [{
                'id': str(e.id),
                'date': e.recorded_at.isoformat() if e.recorded_at else None,
                # LedgerEntry has no `note` field, only `description`
                'description': e.description or 'N/A',
                'category': e.category or 'Uncategorized',
                'transaction_type': e.transaction_type,
                'amount': _f(e.amount),
                'member': e.member.full_name if e.member else None,
                'recorded_by': e.recorded_by.get_full_name() if e.recorded_by else 'System',
                'is_verified': e.is_verified,
            } for e in rows],
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

        # "Excused" only exists if the Attendance model actually tracks it
        field_names = {f.name for f in Attendance._meta.get_fields()}
        excused = attendance.filter(excused=True).count() if 'excused' in field_names else None

        return {
            'total_meetings': total_meetings,
            'present': attended,
            'absent': not_attended,
            'excused': excused,
            'attended': attended,
            'not_attended': not_attended,
            'attendance_rate': (attended / (attended + not_attended) * 100) if (attended + not_attended) > 0 else 0,
            'by_member': self.get_attendance_by_member(attendance),
        }

    def get_attendance_by_member(self, attendance):
        result = {}
        for record in attendance.select_related('member'):
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
            transaction_date__gte=self.start_date,
            transaction_date__lte=self.end_date
        )
        total_savings = (
            _total(savings.filter(transaction_type='deposit'))
            - _total(savings.filter(transaction_type='withdrawal'))
        )

        loans = Loan.objects.filter(
            member=member,
            created_at__gte=self.start_date,
            created_at__lte=self.end_date
        )
        total_loans = _total(loans)

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

    def _outstanding_loan_balance(self):
        """What is still owed on all disbursed, unfinished loans of the group (as of now)"""
        total = 0.0
        for loan in Loan.objects.filter(group=self.group):
            if self._is_disbursed(loan) and loan.status != 'completed':
                total += max(self._loan_payable(loan) - self._loan_paid(loan), 0.0)
        return total

    def get_financial_summary(self):
        ledger = self._ledger_qs()
        savings = self._savings_qs()

        deposits = _total(savings.filter(transaction_type='deposit'))
        withdrawals = _total(savings.filter(transaction_type='withdrawal'))
        social = _total(ledger.filter(transaction_type='social_contribution'))
        credit = _total(ledger.filter(transaction_type__in=CREDIT_TYPES))
        debit = _total(ledger.exclude(transaction_type__in=CREDIT_TYPES))

        end = self.end_date.date() if isinstance(self.end_date, datetime) else self.end_date

        return {
            'total_savings': deposits - withdrawals,        # net savings
            'savings_balance': self._savings_balance(),     # to date
            'total_social_fund': social,
            'total_loans_disbursed': _total(ledger.filter(transaction_type='loan_disbursement')),
            'total_repaid': _total(ledger.filter(transaction_type='loan_repayment')),
            'outstanding_balance': self._outstanding_loan_balance(),
            'total_transactions_debit': debit,
            'total_transactions_credit': credit,
            'net_transactions': credit - debit,
            'total_contributions': deposits + social,
            'ledger_balance': _f(LedgerEntry.get_balance(self.group, as_of_date=end)),
        }