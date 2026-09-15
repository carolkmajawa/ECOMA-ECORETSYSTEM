# apps/groups/signals.py - COMPLETE WORKING VERSION
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from .models import LedgerEntry

# Import models from other apps
from apps.savings.models import Saving
from apps.loans.models import Loan, LoanRepayment
from apps.attendance.models import Attendance

logger = logging.getLogger(__name__)


# ==================== SAVINGS SIGNAL ====================
@receiver(post_save, sender=Saving)
def create_savings_ledger_entry(sender, instance, created, **kwargs):
    """Auto-create ledger entry when a savings transaction is created"""
    if created:
        try:
            # Check if ledger entry already exists for this saving
            existing = LedgerEntry.objects.filter(
                source_model='savings',
                source_id=instance.id,
                is_deleted=False
            ).exists()
            
            if not existing:
                member = instance.member
                group = member.group
                
                # Determine transaction type
                transaction_type = 'savings_contribution' if instance.transaction_type == 'deposit' else 'withdrawal'
                
                # FIXED: Convert UUID to string FIRST, then slice
                saving_id_str = str(instance.id)
                
                # Create the ledger entry
                LedgerEntry.objects.create(
                    group=group,
                    transaction_type=transaction_type,
                    category='savings',
                    amount=instance.amount,
                    member=member,
                    description=f"{'Deposit' if instance.transaction_type == 'deposit' else 'Withdrawal'} by {member.full_name}",
                    reference_number=instance.reference_number or f"SAV-{saving_id_str[:8]}",
                    recorded_by=instance.recorded_by,
                    is_auto_generated=True,
                    source_model='savings',
                    source_id=instance.id,
                )
                logger.info(f"Auto-created ledger entry for savings {instance.id}")
                
        except Exception as e:
            logger.error(f"Error creating ledger entry for savings: {e}")


# ==================== LOAN SIGNALS ====================
@receiver(post_save, sender=Loan)
def create_loan_ledger_entry(sender, instance, created, **kwargs):
    """Auto-create ledger entry when a loan is disbursed"""
    if instance.status == 'active' and instance.amount > 0:
        try:
            existing = LedgerEntry.objects.filter(
                source_model='loan',
                source_id=instance.id,
                transaction_type='loan_disbursement',
                is_deleted=False
            ).exists()
            
            if not existing:
                group = instance.group
                member = instance.member
                
                # FIXED: Convert UUID to string FIRST, then slice
                loan_id_str = str(instance.id)
                
                LedgerEntry.objects.create(
                    group=group,
                    transaction_type='loan_disbursement',
                    category='loans',
                    amount=instance.amount,
                    member=member,
                    loan=instance,
                    description=f"Loan disbursement to {member.full_name} - {instance.loan_type}",
                    reference_number=f"L-{loan_id_str[:8]}",
                    recorded_by=instance.approved_by,
                    is_auto_generated=True,
                    source_model='loan',
                    source_id=instance.id,
                )
                logger.info(f"Auto-created ledger entry for loan disbursement {instance.id}")
        except Exception as e:
            logger.error(f"Error creating ledger entry for loan: {e}")


@receiver(post_save, sender=LoanRepayment)
def create_repayment_ledger_entry(sender, instance, created, **kwargs):
    """Auto-create ledger entry when a loan repayment is made"""
    if created and instance.amount > 0:
        try:
            existing = LedgerEntry.objects.filter(
                source_model='loan_repayment',
                source_id=instance.id,
                is_deleted=False
            ).exists()
            
            if not existing:
                loan = instance.loan
                group = loan.group
                member = loan.member
                
                # FIXED: Convert UUID to string FIRST, then slice
                loan_id_str = str(loan.id)
                today_str = timezone.now().strftime('%Y%m%d')
                
                LedgerEntry.objects.create(
                    group=group,
                    transaction_type='loan_repayment',
                    category='loans',
                    amount=instance.amount,
                    member=member,
                    loan=loan,
                    description=f"Loan repayment by {member.full_name} - {str(loan.id)[:8]}",
                    reference_number=f"REP-{loan_id_str[:8]}-{today_str}",
                    recorded_by=instance.recorded_by,
                    is_auto_generated=True,
                    source_model='loan_repayment',
                    source_id=instance.id,
                )
                logger.info(f"Auto-created ledger entry for repayment {instance.id}")
                
                # Record interest if paid
                if hasattr(instance, 'interest_paid') and instance.interest_paid and instance.interest_paid > 0:
                    LedgerEntry.objects.create(
                        group=group,
                        transaction_type='loan_interest',
                        category='loans',
                        amount=instance.interest_paid,
                        member=member,
                        loan=loan,
                        description=f"Loan interest payment by {member.full_name} - {loan.loan_number}",
                        reference_number=f"INT-{loan_id_str[:8]}-{today_str}",
                        recorded_by=instance.recorded_by,
                        is_auto_generated=True,
                        source_model='loan_repayment',
                        source_id=instance.id,
                    )
                    logger.info(f"Auto-created ledger entry for interest {instance.id}")
        except Exception as e:
            logger.error(f"Error creating ledger entry for repayment: {e}")


# ==================== ATTENDANCE SIGNALS ====================
@receiver(post_save, sender=Attendance)
def create_attendance_ledger_entry(sender, instance, created, **kwargs):
    """Auto-create ledger entry when attendance fine is recorded"""
    if created and hasattr(instance, 'fine_amount') and instance.fine_amount and instance.fine_amount > 0:
        try:
            existing = LedgerEntry.objects.filter(
                source_model='attendance',
                source_id=instance.id,
                transaction_type='meeting_fine',
                is_deleted=False
            ).exists()
            
            if not existing:
                member = instance.member
                group = member.group
                
                # FIXED: Convert UUID to string FIRST, then slice
                attendance_id_str = str(instance.id)
                
                LedgerEntry.objects.create(
                    group=group,
                    transaction_type='meeting_fine',
                    category='fines',
                    amount=instance.fine_amount,
                    member=member,
                    description=f"Meeting fine for {member.full_name}",
                    reference_number=f"FINE-{attendance_id_str[:8]}",
                    recorded_by=instance.recorded_by,
                    is_auto_generated=True,
                    source_model='attendance',
                    source_id=instance.id,
                )
                logger.info(f"Auto-created ledger entry for attendance fine {instance.id}")
        except Exception as e:
            logger.error(f"Error creating ledger entry for attendance: {e}")