"""
Loan terms -- fetched directly from the existing loans app.

This does NOT reimplement anything from apps.loans. It reads the exact
same LoanSettings fields, in the exact same way, as
apps.loans.views.LoanViewSet.create():

    loan_settings = LoanSettings.objects.get(group=group)
    interest_rate = loan_settings.default_interest_rate
    if loan_type == 'group_loan':
        duration_months = loan_settings.group_loan_duration_months
        max_amount = loan_settings.group_loan_max_amount
        min_amount = loan_settings.group_loan_min_amount
    else:
        duration_months = loan_settings.ecoret_loan_duration_months
        max_amount = loan_settings.ecoret_loan_max_amount
        min_amount = loan_settings.ecoret_loan_min_amount

The only things added here are (a) a named exception instead of a
DRF Response for the "not configured" case, since USSD needs a plain
string back, not an HTTP response, and (b) the OTP-issuing/verifying
functions, which are USSD-specific and have no equivalent in
apps.loans (USSDOTP / USSDLoanRequest live in apps.ussd, not
apps.loans).
"""
import uuid
import logging

from django.utils import timezone

from apps.loans.models import LoanSettings
from ..models import USSDOTP, USSDLoanRequest
from .logging_utils import log_safe

logger = logging.getLogger(__name__)


class LoanSettingsNotConfigured(Exception):
    """Mirrors the error apps.loans.views.LoanViewSet.create() already
    returns when LoanSettings.DoesNotExist for the group."""


def get_loan_terms(group, loan_type):
    """Returns (min_amount, max_amount, interest_rate, duration_months)
    read straight off the group's LoanSettings row -- same fields, same
    branch on loan_type, as the web app's loan-creation endpoint."""
    try:
        settings = LoanSettings.objects.get(group=group)
    except LoanSettings.DoesNotExist:
        raise LoanSettingsNotConfigured(
            'Loan settings not configured for this group. '
            'Please ask the chairman to set up loan settings.'
        )

    interest_rate = settings.default_interest_rate

    if loan_type == 'group_loan':
        return (settings.group_loan_min_amount, settings.group_loan_max_amount,
                interest_rate, settings.group_loan_duration_months)

    return (settings.ecoret_loan_min_amount, settings.ecoret_loan_max_amount,
            interest_rate, settings.ecoret_loan_duration_months)


def calculate_total_payable(amount, interest_rate):
    """Same formula LoanViewSet.create() uses: amount * (1 + rate/100)."""
    return amount * (1 + interest_rate / 100)


# ------------------------------------------------------------------
# USSD-specific: OTP issuance/verification. No equivalent exists in
# apps.loans -- the web app doesn't need an OTP step, only USSD does,
# because there's no other way to confirm intent on a feature phone.
# ------------------------------------------------------------------

OTP_VALIDITY_MINUTES = 5


def issue_loan_otp(*, phone_number, member_id, amount, loan_type):
    """Creates the OTP + a pending USSDLoanRequest, returns the OTP
    code so the caller can send it by SMS. The code is only ever
    returned here and sent via SMS -- never logged."""
    otp_code = ''.join(__import__('random').choices('0123456789', k=6))
    correlation_id = str(uuid.uuid4())

    USSDOTP.objects.create(
        phone_number=phone_number,
        otp_code=otp_code,
        purpose='loan_approval',
        expires_at=timezone.now() + timezone.timedelta(minutes=OTP_VALIDITY_MINUTES),
        correlation_id=correlation_id,
    )
    USSDLoanRequest.objects.create(
        member_id=member_id,
        amount=amount,
        loan_type=loan_type,
        otp_session_id=correlation_id,
        status='pending_otp',
    )
    log_safe("Loan OTP issued", member_id=member_id, amount=str(amount),
             loan_type=loan_type, correlation_id=correlation_id)
    return otp_code, correlation_id


def verify_loan_otp(*, phone_number, otp_code):
    """Returns the matched USSDOTP record, or None. Never logs the
    candidate code."""
    record = USSDOTP.objects.filter(
        phone_number=phone_number,
        otp_code=otp_code,
        purpose='loan_approval',
        is_used=False,
        expires_at__gt=timezone.now(),
    ).first()

    if not record:
        log_safe("OTP verification failed", phone_number=phone_number)
        return None

    record.is_used = True
    record.save()
    return record


def get_pending_loan_request(*, member_id, correlation_id):
    return USSDLoanRequest.objects.filter(
        member_id=member_id,
        otp_session_id=correlation_id,
        status='pending_otp',
    ).first()
