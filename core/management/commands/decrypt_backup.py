from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.utils import decrypt_bytes


class Command(BaseCommand):
    help = "Decrypt a DataSnapper backup archive."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the .tar.gz.enc backup")
        parser.add_argument("--output", help="Output path (default: input without .enc)")

    def handle(self, *args, **options):
        source = Path(options["path"])
        if not source.exists():
            raise CommandError(f"Backup not found: {source}")
        output = Path(options["output"]) if options["output"] else source.with_suffix("")
        try:
            output.write_bytes(decrypt_bytes(source.read_bytes()))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Decrypted to {output}"))
