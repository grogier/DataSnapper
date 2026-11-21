import tarfile

import pytest
from django.core.management import call_command


@pytest.mark.django_db(transaction=True)
def test_backup_contains_keys_and_decrypts(tmp_path, settings):
    # Exercise the real key-file path instead of the configured key.
    settings.FIELD_ENCRYPTION_KEY = ""
    (settings.DATA_DIR / "secret.key").write_text("test-secret", encoding="utf-8")

    call_command("backup", "--no-encrypt", verbosity=0)
    plain = list(settings.BACKUP_DIR.glob("*.tar.gz"))
    assert plain
    with tarfile.open(plain[0], "r:gz") as tar:
        names = tar.getnames()
    assert "datasnapper.sqlite3" in names
    assert "field.key" in names
    assert "secret.key" in names
    assert oct(plain[0].stat().st_mode & 0o777) == oct(0o600)

    call_command("backup", verbosity=0)
    encrypted = list(settings.BACKUP_DIR.glob("*.enc"))
    assert encrypted
    assert oct(encrypted[0].stat().st_mode & 0o777) == oct(0o600)

    output = tmp_path / "restored.tar.gz"
    call_command("decrypt_backup", str(encrypted[0]), output=str(output), verbosity=0)
    assert output.read_bytes()[:2] == b"\x1f\x8b"
