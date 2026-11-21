from django.core.management.base import BaseCommand

from audit.services import verify_chain


class Command(BaseCommand):
    help = "Verify the audit log hash chain."

    def handle(self, *args, **options):
        ok, bad_id = verify_chain()
        if ok:
            self.stdout.write(self.style.SUCCESS("Audit chain is intact."))
        else:
            self.stderr.write(self.style.ERROR(f"Audit chain is broken at entry id {bad_id}."))
            raise SystemExit(1)
