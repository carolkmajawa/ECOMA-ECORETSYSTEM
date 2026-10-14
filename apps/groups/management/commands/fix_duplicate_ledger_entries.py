from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.groups.models import LedgerEntry
from apps.savings.models import Saving

# Same rule LedgerEntry.save() uses for the running balance
CREDIT_TYPES = {
    'savings_contribution', 'social_contribution', 'loan_repayment',
    'loan_interest', 'income', 'refund', 'deposit',
}


class Command(BaseCommand):
    help = (
        'Soft-delete ledger entries that were auto-created from a Saving which '
        'itself was copied from a ledger entry (the duplicate deposits), then '
        'recalculate the running balances.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would change without writing anything')
        parser.add_argument('--all-groups', action='store_true',
                            help='Recalculate balances for every group, not just affected ones')

    def handle(self, *args, **opts):
        dry = opts['dry_run']

        # Savings that were copied FROM the ledger by the sync
        mirrored_ids = list(
            Saving.objects.filter(ledger_entry__isnull=False).values_list('id', flat=True)
        )

        dupes = (
            LedgerEntry.objects
            .filter(
                is_deleted=False,
                is_auto_generated=True,
                source_model__icontains='saving',
                source_id__in=mirrored_ids,
            )
            .select_related('group', 'member')
            .order_by('recorded_at')
        )

        affected_groups = set()
        removed = 0
        for d in dupes:
            self.stdout.write(
                f'duplicate: {d.group} | {d.member} | {d.transaction_type} | '
                f'{d.amount} | {d.reference_number}'
            )
            affected_groups.add(d.group_id)
            removed += 1
            if not dry:
                # update() on purpose: no signals, no save() side effects
                LedgerEntry.objects.filter(pk=d.pk).update(
                    is_deleted=True, deleted_at=timezone.now()
                )

        if opts['all_groups']:
            group_ids = set(LedgerEntry.objects.values_list('group_id', flat=True))
        else:
            group_ids = affected_groups

        for group_id in group_ids:
            self._recalculate(group_id, dry)

        self.stdout.write(self.style.SUCCESS(
            f'duplicates={removed} groups_recalculated={len(group_ids)}'
            + ('  (dry run, nothing written)' if dry else '')
        ))

    def _recalculate(self, group_id, dry):
        running = Decimal('0')
        changed = 0
        entries = (
            LedgerEntry.objects
            .filter(group_id=group_id, is_deleted=False)
            .order_by('recorded_at', 'id')
        )
        for e in entries:
            running += e.amount if e.transaction_type in CREDIT_TYPES else -e.amount
            if e.balance != running:
                changed += 1
                if not dry:
                    LedgerEntry.objects.filter(pk=e.pk).update(balance=running)

        name = (
            LedgerEntry.objects.filter(group_id=group_id)
            .select_related('group').first().group
        )
        self.stdout.write(f'balance {name}: final={running}  rows_corrected={changed}')