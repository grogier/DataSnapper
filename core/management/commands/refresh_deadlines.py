from django.core.management.base import BaseCommand

from cases.models import Case
from core.utils import add_months


class Command(BaseCommand):
    help = "Fill in missing due dates from sent dates and extension notices."

    def handle(self, *args, **options):
        updated = 0
        for case in Case.objects.exclude(sent_at=None):
            changed = False
            if not case.due_at:
                case.due_at = add_months(case.sent_at, 1)
                changed = True
            if case.extension_notice_at and not case.extended_due_at:
                case.extended_due_at = add_months(case.sent_at, 3)
                changed = True
            if changed:
                case.save(update_fields=["due_at", "extended_due_at", "updated_at"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Cases updated: {updated}."))
