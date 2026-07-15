"""
Logging helpers.

Fix for: "worth checking [the PIN is] never logged (the code does log
fairly verbosely elsewhere)".

The original view logs request/session state at almost every branch
(`logger.info(f"...{text}...")`, `logger.info(f"Session current_menu...")`,
etc.) which is great for debugging a USSD state machine but means any
dict that happens to contain a PIN, OTP, or raw payload will eventually
get logged by something upstream or downstream of the line that
introduced it. Rather than trust every call site to remember not to
log the wrong field, we make redaction the responsibility of one
choke point.

Usage:
    log_safe("Case payment initiated", case_id=case_id, amount=amount)
    log_safe("Payload received", **payload)   # any 'pin'/'otp' key is masked
"""
import logging

logger = logging.getLogger(__name__)

# Any key (case-insensitive) matching one of these is masked before it
# is ever formatted into a log line.
_SENSITIVE_KEYS = {
    'pin', 'otp', 'otp_code', 'password', 'card_number', 'cvv',
    'account_number', 'secret', 'token',
}


def redact(data):
    """Return a shallow copy of a dict with sensitive fields masked.

    Non-dict input is returned unchanged (so callers can pass through
    arbitrary values without special-casing).
    """
    if not isinstance(data, dict):
        return data
    return {
        key: ('***REDACTED***' if key.lower() in _SENSITIVE_KEYS else value)
        for key, value in data.items()
    }


def log_safe(message, level='info', **fields):
    """Log `message` plus structured fields, redacting sensitive ones first.

    Prefer this over f-string logging of raw dicts/payloads anywhere a
    USSD session's `data` blob, a webhook body, or a payment payload is
    involved, since those are exactly the places a PIN/OTP tends to
    hitch a ride.
    """
    safe_fields = redact(fields)
    getattr(logger, level)("%s | %s", message, safe_fields)