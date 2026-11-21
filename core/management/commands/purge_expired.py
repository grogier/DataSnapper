from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from cases.models import Case
from core.models import AppSettings


class Command(BaseCommand):
    help = "Delete closed cases older than the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Actually delete. Without this flag the command only reports.",
        )

    def handle(self, *args, **options):
        retention = AppSettings.load().retention_days
        if retention <= 0:
            self.stdout.write("Retention is disabled (retention_days = 0).")
            return
        cutoff = timezone.localdate() - timedelta(days=retention)
        cases = Case.objects.filter(
            status__in=[Case.Status.CLOSED, Case.Status.WITHDRAWN],
            closed_at__lt=cutoff,
        )
        count = cases.count()
        if not options["yes"]:
            self.stdout.write(f"{count} case(s) would be deleted (cutoff {cutoff}).")
            return
        for case in cases:
            for attachment in case.attachments.all():
                if attachment.file:
                    attachment.file.delete(save=False)
                if attachment.encrypted_file:
                    attachment.encrypted_file.delete(save=False)
            case.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} case(s)."))
