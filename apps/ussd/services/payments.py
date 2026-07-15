"""
Mobile-money payment service.

Fix for: "handle_case_payment takes a 'mobile money PIN' as plain text
over USSD ... worth checking [it's not needed at all, since] STK push
confirmation happens on-device, not via USSD text."

That's exactly what's changed here: there is no `pin` parameter
anywhere in this module. An STK Push already pops a native prompt on
the subscriber's own handset (via their mobile money app/menu) asking
them to confirm and enter their PIN *there*. Piping a PIN through the
USSD session first adds a step that:
  1. isn't required by the payment provider,
  2. puts a credential through a channel (USSD `text`, Django request
     logs, session.data) that has no reason to ever see it, and
  3. is unencrypted/plaintext at the telco level in a lot of USSD
     deployments.

So the old `case_payment_pin` USSD screen is gone. Selecting something
to pay for goes straight to `start_stk_push`, which only needs an
amount, a reference, and who to charge.
"""
from decimal import Decimal
import uuid
import logging

from apps.security.models import MobileMoneyTransaction, TransactionAudit
from apps.security.services.paychangu import paychangu
from .logging_utils import log_safe

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Raised when a payment cannot be initiated or completed.
    Callers translate this into a user-facing 'END ...' message."""


class PaymentService:
    def start_stk_push(self, *, member, amount, payment_type, payload=None):
        """Kick off an STK Push. No PIN is collected or stored here —
        the subscriber confirms on their own phone."""
        phone_number = member.phone_number
        if member.user and getattr(member.user, 'phone_number', None):
            phone_number = member.user.phone_number

        reference = f"ECORET-{payment_type.upper()}-{uuid.uuid4().hex[:8].upper()}"

        try:
            payment_result = paychangu.initiate_payment(
                phone_number=phone_number,
                amount=Decimal(str(amount)),
                reference=reference,
                customer_name=member.full_name,
            )
        except Exception as exc:
            # Log identifying info only — never the raw provider payload,
            # which may itself contain secrets on the provider's side.
            log_safe("STK push initiation failed", level='error',
                     reference=reference, payment_type=payment_type,
                     amount=str(amount))
            raise PaymentError("Payment could not be started. Please try again later.") from exc

        if not isinstance(payment_result, dict):
            payment_result = {'success': False, 'error': str(payment_result)}

        MobileMoneyTransaction.objects.create(
            group=member.group,
            member=member,
            transaction_type='collection',
            amount=Decimal(str(amount)),
            phone_number=phone_number,
            provider='mpamba',
            reference=reference,
            status='pending',
            transaction_id=payment_result.get('transaction_id'),
            response_data=payment_result,
        )

        return {
            'reference': reference,
            'phone_number': phone_number,
            'payload': payload or {},
        }

    def record_audit(self, *, member, transaction_type, amount, reference, details=None):
        TransactionAudit.objects.create(
            user=member.user,
            group=member.group,
            member=member,
            transaction_type=transaction_type,
            amount=Decimal(str(amount)),
            reference_id=reference,
            status='success',
            details=details or {'payment_reference': reference},
        )

    def mark_transaction_success(self, *, member, reference):
        txn = MobileMoneyTransaction.objects.filter(
            member=member, reference=reference
        ).order_by('-created_at').first()
        if txn:
            txn.status = 'success'
            txn.save(update_fields=['status', 'updated_at'])
        return txn


payment_service = PaymentService()