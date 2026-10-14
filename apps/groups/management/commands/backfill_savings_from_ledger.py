from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.groups.models import LedgerEntry
from apps.groups.services import SAVINGS_TYPE_MAP, sync_entry_to_saving
from apps.savings.models import Saving


class Command(BaseCommand):
    help = 'Copy existing ledger deposits/withdrawals into the savings table'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be copied without writing anything')

    def handle(self, *args, **opts):
        copied = already = suspected = 0

        entries = (
            LedgerEntry.objects
            .filter(is_deleted=False, transaction_type__in=SAVINGS_TYPE_MAP)
            .exclude(is_auto_generated=True, source_model__icontains='saving')
            .select_related('group', 'member')
            .order_by('recorded_at')
        )

        for e in entries:
            if Saving.objects.filter(ledger_entry=e).exists():
                already += 1
                continue

            ref = e.reference_number
            same = Saving.objects.filter(
                group=e.group,
                member=e.member,
                amount=e.amount,
                transaction_type=SAVINGS_TYPE_MAP[e.transaction_type],
            ).filter(
                Q(reference_number=ref) if ref
                else Q(transaction_date__date=e.recorded_at.date())
            )
            if same.exists():
                suspected += 1
                self.stdout.write(
                    f'POSSIBLE DUPLICATE, skipped: {e.group} | {e.member} | {e.amount} | {ref}'
                )
                continue

            self.stdout.write(
                f'copy: {e.group} | {e.member} | {e.transaction_type} | {e.amount} | {ref}'
            )
            if not opts['dry_run']:
                sync_entry_to_saving(e)
            copied += 1

        self.stdout.write(self.style.SUCCESS(
            f'copied={copied} already_linked={already} possible_duplicates={suspected}'
            + ('  (dry run, nothing written)' if opts['dry_run'] else '')
        ))