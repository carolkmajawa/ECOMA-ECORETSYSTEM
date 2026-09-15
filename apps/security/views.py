# apps/payments/views.py
import uuid
import logging
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, request
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes

from apps.groups.models import GroupMember, Group
from apps.savings.models import Saving
from apps.loans.models import Loan, LoanRepayment
from .models import TransactionAudit, MobileMoneyTransaction
from .services.paychangu import  PayChanguService
import hmac
import hashlib
from django.conf import settings

logger = logging.getLogger(__name__)

def verify_paychangu_signature(request):
    """Verify the webhook genuinely came from PayChangu using their
    HMAC-SHA256 signature scheme: hash the raw request body with our
    shared webhook secret and compare against the 'Signature' header.
    """
    secret = settings.PAYCHANGU_WEBHOOK_SECRET
    if not secret:
        logger.error("PAYCHANGU_WEBHOOK_SECRET is not configured - rejecting webhook")
        return False

    signature_header = request.headers.get('Signature', '')
    if not signature_header:
        return False

    computed_signature = hmac.new(
        secret.encode('utf-8'),
        request.body,  # raw bytes, exactly as PayChangu signed it
        hashlib.sha256
    ).hexdigest()

    # constant-time comparison to avoid timing attacks
    return hmac.compare_digest(computed_signature, signature_header)


class InitiatePayoutView(APIView):
    """
    Initiate a mobile money payout to a member
    Only chairman, treasurer, or admin can initiate payouts
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Check permissions
        if user.role not in ['admin', 'chairman', 'treasurer']:
            return Response(
                {'error': 'You do not have permission to initiate payouts'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        member_id = request.data.get('member_id')
        amount = request.data.get('amount')
        purpose = request.data.get('purpose', 'Payout')
        
        if not member_id or not amount:
            return Response(
                {'error': 'member_id and amount are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                return Response(
                    {'error': 'Amount must be greater than 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get member
        member = get_object_or_404(GroupMember, id=member_id, is_active=True)
        group = member.group
        
        # Check if user has access to this group
        if user.role != 'admin' and user not in [group.chairman, group.treasurer]:
            return Response(
                {'error': 'You do not have access to this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if member has mobile money
        if not member.mobile_money_number:
            return Response(
                {'error': 'Member does not have mobile money set up'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate reference
        reference = f"PAYOUT-{uuid.uuid4().hex[:8].upper()}"
        
        # Create transaction record
        transaction = MobileMoneyTransaction.objects.create(
            group=group,
            member=member,
            transaction_type='payout',
            amount=amount,
            phone_number=member.mobile_money_number,
            provider=member.mobile_money_provider or 'mpesa',
            reference=reference,
            status='pending'
        )
        
        # Create audit log
        TransactionAudit.objects.create(
            user=user,
            group=group,
            member=member,
            transaction_type='mobile_money_payout',
            amount=amount,
            reference_id=reference,
            status='pending',
            details={
                'purpose': purpose,
                'phone_number': member.mobile_money_number,
                'provider': member.mobile_money_provider
            }
        )
        
        # Initiate payout with PayChangu
        result = PayChanguService.initiate_payout(
            phone_number=member.mobile_money_number,
            amount=amount,
            reference=reference,
            customer_name=member.full_name
        )
        
        if result['success']:
            transaction.status = 'processing'
            transaction.transaction_id = result.get('transaction_id')
            transaction.response_data = result.get('response', {})
            transaction.save()
            
            # Update audit
            TransactionAudit.objects.filter(reference_id=reference).update(
                status='processing'
            )
            
            return Response({
                'success': True,
                'message': 'Payout initiated successfully',
                'reference': reference,
                'transaction_id': transaction.transaction_id,
                'status': transaction.status
            }, status=status.HTTP_200_OK)
        else:
            transaction.status = 'failed'
            transaction.error_message = result.get('error', 'Unknown error')
            transaction.save()
            
            # Update audit
            TransactionAudit.objects.filter(reference_id=reference).update(
                status='failed',
                error_message=transaction.error_message
            )
            
            return Response({
                'success': False,
                'error': result.get('error', 'Failed to initiate payout')
            }, status=status.HTTP_400_BAD_REQUEST)


class InitiatePaymentView(APIView):
    """
    Initiate a mobile money collection from a member
    Only chairman, treasurer, or admin can initiate collections
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Check permissions
        if user.role not in ['admin', 'chairman', 'treasurer']:
            return Response(
                {'error': 'You do not have permission to initiate collections'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        member_id = request.data.get('member_id')
        amount = request.data.get('amount')
        purpose = request.data.get('purpose', 'Collection')
        
        if not member_id or not amount:
            return Response(
                {'error': 'member_id and amount are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                return Response(
                    {'error': 'Amount must be greater than 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get member
        member = get_object_or_404(GroupMember, id=member_id, is_active=True)
        group = member.group
        
        # Check if user has access to this group
        if user.role != 'admin' and user not in [group.chairman, group.treasurer]:
            return Response(
                {'error': 'You do not have access to this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if member has mobile money
        if not member.mobile_money_number:
            return Response(
                {'error': 'Member does not have mobile money set up'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate reference
        reference = f"COLLECT-{uuid.uuid4().hex[:8].upper()}"
        
        # Create transaction record
        transaction = MobileMoneyTransaction.objects.create(
            group=group,
            member=member,
            transaction_type='collection',
            amount=amount,
            phone_number=member.mobile_money_number,
            provider=member.mobile_money_provider or 'mpesa',
            reference=reference,
            status='pending'
        )
        
        # Create audit log
        TransactionAudit.objects.create(
            user=user,
            group=group,
            member=member,
            transaction_type='mobile_money_collection',
            amount=amount,
            reference_id=reference,
            status='pending',
            details={
                'purpose': purpose,
                'phone_number': member.mobile_money_number,
                'provider': member.mobile_money_provider
            }
        )
        
        # Initiate payment with PayChangu
        result = PayChanguService.initiate_payment(
            phone_number=member.mobile_money_number,
            amount=amount,
            reference=reference,
            customer_name=member.full_name
        )
        
        if result['success']:
            transaction.status = 'processing'
            transaction.transaction_id = result.get('transaction_id')
            transaction.response_data = result.get('response', {})
            transaction.save()
            
            # Update audit
            TransactionAudit.objects.filter(reference_id=reference).update(
                status='processing'
            )
            
            return Response({
                'success': True,
                'message': 'Collection initiated successfully',
                'reference': reference,
                'transaction_id': transaction.transaction_id,
                'status': transaction.status
            }, status=status.HTTP_200_OK)
        else:
            transaction.status = 'failed'
            transaction.error_message = result.get('error', 'Unknown error')
            transaction.save()
            
            # Update audit
            TransactionAudit.objects.filter(reference_id=reference).update(
                status='failed',
                error_message=transaction.error_message
            )
            
            return Response({
                'success': False,
                'error': result.get('error', 'Failed to initiate collection')
            }, status=status.HTTP_400_BAD_REQUEST)


class TransactionStatusView(APIView):
    """
    Check the status of a mobile money transaction
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        reference = request.query_params.get('reference')
        
        if not reference:
            return Response(
                {'error': 'reference is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get transaction from database
        try:
            transaction = MobileMoneyTransaction.objects.get(reference=reference)
        except MobileMoneyTransaction.DoesNotExist:
            return Response(
                {'error': 'Transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify with PayChangu
        result = PayChanguService.verify_transaction(reference)
        
        if result['success']:
            status_map = {
                'pending': 'pending',
                'processing': 'processing',
                'completed': 'success',
                'failed': 'failed',
                'cancelled': 'cancelled'
            }
            paychangu_status = result.get('status', 'pending')
            transaction.status = status_map.get(paychangu_status, 'pending')
            transaction.response_data = result.get('transaction', {})
            transaction.save()
            
            return Response({
                'reference': reference,
                'status': transaction.status,
                'amount': transaction.amount,
                'phone_number': transaction.phone_number,
                'created_at': transaction.created_at,
                'updated_at': transaction.updated_at,
                'transaction_id': transaction.transaction_id
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'reference': reference,
                'status': transaction.status,
                'error': result.get('error', 'Failed to verify transaction')
            }, status=status.HTTP_200_OK)


class TransactionHistoryView(APIView):
    """
    Get transaction history for a member or group
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        member_id = request.query_params.get('member_id')
        group_id = request.query_params.get('group_id')
        transaction_type = request.query_params.get('transaction_type')
        status_filter = request.query_params.get('status')
        
        # Build queryset
        queryset = MobileMoneyTransaction.objects.all()
        
        # Filter by user permissions
        if user.role == 'admin':
            pass  # Admin can see all
        elif member_id:
            member = get_object_or_404(GroupMember, id=member_id)
            if user not in [member.group.chairman, member.group.treasurer]:
                return Response(
                    {'error': 'You do not have access to this member\'s transactions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            queryset = queryset.filter(member=member)
        elif group_id:
            group = get_object_or_404(Group, id=group_id)
            if user.role != 'admin' and user not in [group.chairman, group.treasurer]:
                return Response(
                    {'error': 'You do not have access to this group\'s transactions'},
                    status=status.HTTP_403_FORBIDDEN
                )
            queryset = queryset.filter(group=group)
        else:
            # User can only see their own transactions
            groups = user.chairman_groups.all() | user.treasurer_groups.all()
            queryset = queryset.filter(group__in=groups)
        
        # Apply filters
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Limit to last 100
        queryset = queryset[:100]
        
        # Prepare response
        data = []
        for transaction in queryset:
            data.append({
                'reference': transaction.reference,
                'transaction_type': transaction.transaction_type,
                'amount': str(transaction.amount),
                'phone_number': transaction.phone_number,
                'provider': transaction.provider,
                'status': transaction.status,
                'member': {
                    'id': str(transaction.member.id),
                    'full_name': transaction.member.full_name
                },
                'group': transaction.group.group_name,
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat()
            })
        
        return Response({
            'count': len(data),
            'transactions': data
        }, status=status.HTTP_200_OK)


class BalanceView(APIView):
    """
    Check PayChangu account balance
    Only admin can check balance
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'admin':
            return Response(
                {'error': 'Only ECORET admin can check balance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        result = PayChanguService.check_balance()
        
        if result['success']:
            return Response({
                'success': True,
                'balance': result.get('balance'),
                'currency': result.get('currency', 'MWK')
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Failed to check balance')
            }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def paychangu_webhook(request):
    """
    Webhook endpoint for PayChangu to notify transaction status.
    Verifies the request's HMAC-SHA256 signature before trusting
    anything in the payload - an unverified webhook could otherwise
    let anyone who finds this URL fake a successful payment.
    """
    if not verify_paychangu_signature(request):
        logger.warning("Rejected PayChangu webhook with invalid or missing signature")
        return JsonResponse({'error': 'Invalid signature'}, status=403)

    try:
        data = request.data
        logger.info(f"PayChangu webhook received: {data}")

        reference = data.get('reference')
        webhook_status = data.get('status')
        transaction_id = data.get('transaction_id')

        if not reference:
            return JsonResponse({'error': 'Reference required'}, status=400)

        try:
            transaction = MobileMoneyTransaction.objects.get(reference=reference)
        except MobileMoneyTransaction.DoesNotExist:
            logger.error(f"Transaction not found: {reference}")
            return JsonResponse({'error': 'Transaction not found'}, status=404)

        status_map = {
            'completed': 'success',
            'success': 'success',
            'failed': 'failed',
            'cancelled': 'cancelled',
            'pending': 'pending',
            'processing': 'processing',
        }
        new_status = status_map.get(webhook_status, 'pending')

        # Idempotency guard: if we've already processed this as success,
        # don't create a duplicate repayment/saving/penalty record if
        # PayChangu retries the webhook delivery.
        already_completed = transaction.status == 'success'

        transaction.status = new_status
        transaction.transaction_id = transaction_id or transaction.transaction_id
        # Merge webhook payload into response_data rather than
        # overwriting it, so we don't lose the stashed payment_type/payload.
        merged_response = dict(transaction.response_data or {})
        merged_response['webhook_data'] = data
        transaction.response_data = merged_response
        transaction.save()

        TransactionAudit.objects.filter(reference_id=reference).update(
            status=transaction.status,
            details={'webhook_data': data},
        )

        if new_status == 'success' and not already_completed:
            if transaction.transaction_type == 'payout':
                payout_loan_id = (transaction.response_data or {}).get('_ecoret_payout_loan_id')
                if payout_loan_id:
                    try:
                        loan = Loan.objects.get(id=payout_loan_id)
                        loan.mark_as_disbursed_by_ecoret(
                            'bank_transfer',
                            loan.approved_by,
                            account=None,
                            reference=reference,
                        )
                    except Loan.DoesNotExist:
                        logger.error(f"Payout webhook: loan {payout_loan_id} not found for reference {reference}")
                    except Exception:
                        logger.exception(f"Failed to mark loan {payout_loan_id} as disbursed for reference {reference}")

            elif transaction.transaction_type == 'collection':
                payment_type = (transaction.response_data or {}).get('_ecoret_payment_type')
                payload = (transaction.response_data or {}).get('_ecoret_payload', {}) or {}
                member = transaction.member
                amount = transaction.amount

                try:
                    if payment_type == 'repayment':
                        loan_id = payload.get('loan_id')
                        loan = Loan.objects.get(id=loan_id)
                        LoanRepayment.objects.create(
                            loan=loan,
                            member=member,
                            amount=amount,
                            principal_paid=amount,
                            interest_paid=0,
                            payment_method='mobile_money',
                            transaction_reference=reference,
                        )
                        if loan.get_balance() <= 0:
                            loan.status = 'completed'
                            loan.save()

                    elif payment_type == 'savings':
                        Saving.objects.create(
                            group=transaction.group,
                            member=member,
                            amount=amount,
                            saving_type='voluntary',
                            transaction_type='deposit',
                            reference_number=reference,
                            notes='USSD Mobile Money Deposit',
                        )

                    elif payment_type == 'case_penalty':
                        from apps.attendance.models import AttendanceCase, PenaltyPayment
                        from django.utils import timezone as tz

                        case_id = payload.get('case_id')
                        case = AttendanceCase.objects.get(id=case_id)
                        case.penalty_paid += amount
                        if case.penalty_paid >= case.penalty_amount:
                            case.status = 'resolved'
                            case.resolved_by = member.user
                            case.resolved_at = tz.now()
                        case.save()

                        PenaltyPayment.objects.create(
                            attendance_case=case,
                            member=member,
                            amount=amount,
                            payment_method='mobile_money',
                            transaction_reference=reference,
                            recorded_by=member.user,
                        )
                    else:
                        logger.warning(
                            f"Webhook success for reference {reference} but "
                            f"unknown/missing payment_type: {payment_type!r}"
                        )

                    TransactionAudit.objects.create(
                        user=member.user,
                        group=transaction.group,
                        member=member,
                        transaction_type=f'{payment_type}_completed' if payment_type else 'mobile_money_completed',
                        amount=amount,
                        reference_id=reference,
                        status='success',
                        details={'payment_reference': reference, 'payment_type': payment_type},
                    )

                except Exception:
                    logger.exception(
                        f"Failed to create downstream record for successful "
                        f"payment {reference} (payment_type={payment_type})"
                    )
            # Don't fail the webhook response to PayChangu just
            # because our own record-creation broke - the payment
            # genuinely succeeded on their end. Log loudly instead
            # so this can be fixed/reconciled manually.

        return JsonResponse({'status': 'ok'}, status=200)

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)