import pytest

from audit.models import AuditLog
from audit.services import log, verify_chain


@pytest.mark.django_db
def test_audit_chain_is_valid_and_detects_tampering(user):
    first = log(actor=user, action="test.one", summary="first")
    second = log(actor=user, action="test.two", summary="second")
    assert first.prev_hash == AuditLog.GENESIS_HASH
    assert second.prev_hash == first.entry_hash
    assert verify_chain() == (True, None)

    AuditLog.objects.filter(pk=first.pk).update(summary="tampered")
    ok, bad_id = verify_chain()
    assert ok is False
    assert bad_id == first.pk


@pytest.mark.django_db
def test_case_creation_is_audited(case):
    assert AuditLog.objects.filter(action="case.create", entity_id=str(case.pk)).exists()
