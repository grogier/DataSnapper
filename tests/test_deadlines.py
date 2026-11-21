from datetime import date

import pytest

from cases.models import Case
from cases.services import (
    create_case,
    extend_deadline,
    transition_case,
)
from core.utils import add_months


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 15), 1, date(2026, 2, 15)),
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2024, 1, 31), 1, date(2024, 2, 29)),
        (date(2025, 11, 30), 3, date(2026, 2, 28)),
        (date(2025, 12, 31), 2, date(2026, 2, 28)),
    ],
)
def test_add_months_clamps_to_month_end(start, months, expected):
    assert add_months(start, months) == expected


def test_case_reference_and_checklist(case, organization):
    assert case.reference.startswith("DSAR-")
    assert case.reference.endswith("0001")
    assert case.checklist
    assert "purposes" in case.checklist
    assert case.checklist_total == 10
    assert case.checklist_done == 0


def test_transition_to_sent_starts_deadline(case, user):
    transition_case(case, Case.Status.SENT, actor=user)
    case.refresh_from_db()
    assert case.sent_at is not None
    assert case.due_at == add_months(case.sent_at, 1)
    assert case.events.filter(event_type="status").exists()


def test_invalid_transition_is_rejected(case):
    with pytest.raises(ValueError):
        transition_case(case, Case.Status.FULFILLED)


def test_extension_uses_three_months_from_send(case, user):
    transition_case(case, Case.Status.SENT, actor=user)
    case.refresh_from_db()
    extend_deadline(case, notice_date=case.sent_at, actor=user)
    case.refresh_from_db()
    assert case.extended_due_at == add_months(case.sent_at, 3)
    assert case.effective_due == case.extended_due_at


def test_creating_a_second_case_increments_reference(user, organization):
    first = create_case(organization=organization, right="access", actor=user)
    second = create_case(organization=organization, right="erasure", actor=user)
    assert first.reference != second.reference
    assert int(second.reference.rsplit("-", 1)[1]) == int(first.reference.rsplit("-", 1)[1]) + 1
