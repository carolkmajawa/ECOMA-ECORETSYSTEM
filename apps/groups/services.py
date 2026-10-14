import logging

from django.utils import timezone

from apps.savings.models import Saving

logger = logging.getLogger(__name__)

# ledger transaction_type -> Saving.transaction_type
SAVINGS_TYPE_MAP = {
    'deposit': 'deposit',
    'savings_contribution': 'deposit',
    'withdrawal': 'withdrawal',
}


def _is_savings_sourced(entry):
    """Ledger rows auto-created FROM a Saving must never be copied back."""
    return bool(
        entry.is_auto_generated
        and entry.source_model
        and 'saving' in entry.source_model.lower()
    )


def sync_entry_to_saving(entry):
    """Create, update or remove the Saving that mirrors a ledger entry.

    Saving rows are written with bulk_create() / queryset.update(), which do NOT
    send post_save signals. That stops the existing "Saving -> ledger entry"
    signal from creating a second ledger entry for every deposit.
    """
    saving_type = SAVINGS_TYPE_MAP.get(entry.transaction_type)
    existing = Saving.objects.filter(ledger_entry=entry).first()

    if (
        saving_type is None
        or entry.is_deleted
        or entry.member_id is None
        or _is_savings_sourced(entry)
    ):
        if existing:
            existing.delete()
        return None

    values = dict(
        group=entry.group,
        member=entry.member,
        amount=entry.amount,
        transaction_type=saving_type,
        saving_type='voluntary',
        notes=entry.description or '',
        recorded_by=entry.recorded_by,
    )

    if existing:
        Saving.objects.filter(pk=existing.pk).update(
            transaction_date=entry.recorded_at,
            updated_at=timezone.now(),
            **values,
        )
        return existing

    ref = entry.reference_number or f'LEDGER-{entry.pk}'
    if Saving.objects.filter(reference_number=ref).exists():
        ref = f'{ref}-L{str(entry.pk)[:6]}'

    saving = Saving(ledger_entry=entry, reference_number=ref, **values)
    Saving.objects.bulk_create([saving])  # no post_save signal

    # Keep the original date even if Saving.transaction_date is auto_now_add
    Saving.objects.filter(pk=saving.pk).update(transaction_date=entry.recorded_at)
    return saving
