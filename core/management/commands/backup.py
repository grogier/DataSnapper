from __future__ import annotations

import os
import tarfile
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from core.utils import encrypt_bytes, get_fernet


class Command(BaseCommand):
    help = "Create a consistent SQLite and media backup, encrypted by default."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-encrypt",
            action="store_true",
            help="Write an unencrypted .tar.gz archive instead of a .enc file.",
        )

    def handle(self, *args, **options):
        backup_dir = Path(settings.BACKUP_DIR)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        encrypt = not options["no_encrypt"] and os.environ.get("BACKUP_ENCRYPT", "1") != "0"

        # Create the field key before archiving, otherwise the first backup
        # would be encrypted with a key that is not inside the archive.
        get_fernet()

        with tempfile.TemporaryDirectory(dir=settings.DATA_DIR) as tmp:
            tmp_path = Path(tmp)
            db_copy = tmp_path / "datasnapper.sqlite3"
            escaped = db_copy.as_posix().replace("'", "''")
            with connection.cursor() as cursor:
                cursor.execute(f"VACUUM INTO '{escaped}'")

            archive = tmp_path / f"datasnapper-backup-{stamp}.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(db_copy, arcname="datasnapper.sqlite3")
                media = Path(settings.MEDIA_ROOT)
                if media.exists():
                    tar.add(media, arcname="media")
                # Keep the keys with the archive so a restore on the same
                # installation can decrypt identity documents. Store the field
                # key separately too: without it the archive is unreadable.
                for key_name in ("secret.key", "field.key"):
                    key_path = Path(settings.DATA_DIR) / key_name
                    if key_path.exists():
                        tar.add(key_path, arcname=key_name)

            if encrypt:
                target = backup_dir / f"datasnapper-backup-{stamp}.tar.gz.enc"
                target.write_bytes(encrypt_bytes(archive.read_bytes()))
            else:
                target = backup_dir / archive.name
                target.write_bytes(archive.read_bytes())
            try:
                target.chmod(0o600)
            except OSError:
                pass

        retention = int(os.environ.get("BACKUP_RETENTION", "14"))
        backups = sorted(backup_dir.glob("datasnapper-backup-*"))
        for old in backups[:-retention] if retention > 0 else []:
            old.unlink(missing_ok=True)

        self.stdout.write(self.style.SUCCESS(f"Backup written to {target}"))
        if encrypt:
            self.stdout.write(
                "Decrypt with: python manage.py decrypt_backup "
                f"'{target}' --output /tmp/datasnapper-backup.tar.gz"
            )
        else:
            self.stdout.write("Backup is not encrypted.")
