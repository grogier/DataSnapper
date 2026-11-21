from __future__ import annotations

from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import log
from cases.models import Case, CaseEvent
from cases.rights import initial_checklist
from core.models import AppSettings
from core.utils import add_months

TRANSITIONS: dict[str, list[str]] = {
    Case.Status.DRAFT: [Case.Status.QUEUED, Case.Status.SENT, Case.Status.WITHDRAWN],
    Case.Status.QUEUED: [Case.Status.SENT, Case.Status.WITHDRAWN],
    Case.Status.SENT: [
        Case.Status.ACKNOWLEDGED,
        Case.Status.IDENTITY_CHECK,
        Case.Status.IN_PROGRESS,
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.FULFILLED,
        Case.Status.REFUSED,
        Case.Status.NO_RESPONSE,
        Case.Status.ESCALATED,
        Case.Status.WITHDRAWN,
    ],
    Case.Status.ACKNOWLEDGED: [
        Case.Status.IDENTITY_CHECK,
        Case.Status.IN_PROGRESS,
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.FULFILLED,
        Case.Status.REFUSED,
        Case.Status.NO_RESPONSE,
        Case.Status.ESCALATED,
        Case.Status.WITHDRAWN,
    ],
    Case.Status.IDENTITY_CHECK: [
        Case.Status.IN_PROGRESS,
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.FULFILLED,
        Case.Status.REFUSED,
        Case.Status.NO_RESPONSE,
        Case.Status.ESCALATED,
        Case.Status.WITHDRAWN,
    ],
    Case.Status.IN_PROGRESS: [
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.FULFILLED,
        Case.Status.REFUSED,
        Case.Status.NO_RESPONSE,
        Case.Status.ESCALATED,
        Case.Status.WITHDRAWN,
    ],
    Case.Status.PARTIALLY_FULFILLED: [
        Case.Status.IN_PROGRESS,
        Case.Status.FULFILLED,
        Case.Status.REFUSED,
        Case.Status.ESCALATED,
        Case.Status.CLOSED,
    ],
    Case.Status.REFUSED: [Case.Status.ESCALATED, Case.Status.CLOSED],
    Case.Status.NO_RESPONSE: [Case.Status.ESCALATED, Case.Status.CLOSED],
    Case.Status.ESCALATED: [
        Case.Status.FULFILLED,
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.CLOSED,
    ],
    Case.Status.FULFILLED: [Case.Status.CLOSED, Case.Status.IN_PROGRESS],
    Case.Status.WITHDRAWN: [Case.Status.CLOSED],
    Case.Status.CLOSED: [Case.Status.IN_PROGRESS],
}


def add_event(
    case: Case,
    event_type: str,
    *,
    actor=None,
    summary: str = "",
    detail: str = "",
    metadata: dict | None = None,
) -> CaseEvent:
    return CaseEvent.objects.create(
        case=case,
        event_type=event_type,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        summary=summary[:255],
        detail=detail,
        metadata=metadata or {},
    )


def next_reference(prefix: str) -> str:
    year = timezone.localdate().year
    base = f"{prefix.upper()}-{year}-"
    last = (
        Case.objects.filter(reference__startswith=base)
        .order_by("-reference")
        .values_list("reference", flat=True)
        .first()
    )
    sequence = 1
    if last:
        try:
            sequence = int(last.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            sequence = Case.objects.filter(reference__startswith=base).count() + 1
    return f"{base}{sequence:04d}"


def create_case(
    *,
    organization,
    right: str,
    scope: str = "",
    priority: str = Case.Priority.NORMAL,
    title: str = "",
    notes: str = "",
    jurisdiction: str = "EU",
    actor=None,
    request=None,
) -> Case:
    settings_obj = AppSettings.load()
    for attempt in range(5):
        reference = next_reference(settings_obj.case_prefix)
        try:
            with transaction.atomic():
                case = Case.objects.create(
                    organization=organization,
                    reference=reference,
                    right=right,
                    scope=scope,
                    priority=priority,
                    title=title,
                    notes=notes,
                    jurisdiction=jurisdiction,
                    checklist=initial_checklist(right),
                )
            break
        except IntegrityError:
            if attempt == 4:
                raise
    add_event(
        case,
        CaseEvent.EventType.CREATED,
        actor=actor,
        summary=f"Case created: {case.right_label}",
        detail=scope,
    )
    log(
        actor=actor,
        action="case.create",
        entity_type="case",
        entity_id=str(case.pk),
        summary=f"Created case {case.reference} for {organization.name}",
        metadata={"right": right},
        request=request,
    )
    return case


def transition_case(
    case: Case,
    new_status: str,
    *,
    actor=None,
    note: str = "",
    request=None,
) -> Case:
    if new_status not in TRANSITIONS.get(case.status, []):
        raise ValueError(f"Cannot move a case from {case.status} to {new_status}.")

    today = timezone.localdate()
    previous = case.status

    if new_status == Case.Status.SENT:
        if not case.sent_at:
            case.sent_at = today
        if not case.due_at:
            case.due_at = add_months(case.sent_at, 1)
    elif new_status == Case.Status.ACKNOWLEDGED:
        if not case.received_at:
            case.received_at = today
    elif new_status == Case.Status.IDENTITY_CHECK:
        case.identity_check_at = today
    elif new_status in {
        Case.Status.FULFILLED,
        Case.Status.PARTIALLY_FULFILLED,
        Case.Status.REFUSED,
        Case.Status.NO_RESPONSE,
        Case.Status.WITHDRAWN,
        Case.Status.CLOSED,
    }:
        if new_status in {
            Case.Status.FULFILLED,
            Case.Status.WITHDRAWN,
            Case.Status.CLOSED,
        }:
            case.closed_at = today
        outcome_map = {
            Case.Status.FULFILLED: Case.Outcome.FULFILLED,
            Case.Status.PARTIALLY_FULFILLED: Case.Outcome.PARTIALLY_FULFILLED,
            Case.Status.REFUSED: Case.Outcome.REFUSED,
            Case.Status.WITHDRAWN: Case.Outcome.WITHDRAWN,
            Case.Status.NO_RESPONSE: Case.Outcome.NO_RESPONSE,
        }
        if new_status in outcome_map:
            case.outcome = outcome_map[new_status]

    case.status = new_status
    case.save()

    labels = dict(Case.Status.choices)
    add_event(
        case,
        CaseEvent.EventType.STATUS,
        actor=actor,
        summary=f"Status: {labels[previous]} → {labels[new_status]}",
        detail=note,
        metadata={"from": previous, "to": new_status},
    )
    log(
        actor=actor,
        action="case.status",
        entity_type="case",
        entity_id=str(case.pk),
        summary=f"{case.reference}: {labels[previous]} → {labels[new_status]}",
        metadata={"note": note},
        request=request,
    )
    return case


def extend_deadline(
    case: Case,
    *,
    notice_date: date,
    note: str = "",
    actor=None,
    request=None,
) -> Case:
    if not case.sent_at:
        raise ValueError("Set a sent date before extending the deadline.")
    case.extension_notice_at = notice_date
    case.extended_due_at = add_months(case.sent_at, 3)
    case.save()
    add_event(
        case,
        CaseEvent.EventType.DEADLINE,
        actor=actor,
        summary=f"Deadline extended to {case.extended_due_at:%d-%m-%Y}",
        detail=note,
        metadata={"extended_due_at": case.extended_due_at.isoformat()},
    )
    log(
        actor=actor,
        action="case.deadline_extend",
        entity_type="case",
        entity_id=str(case.pk),
        summary=f"{case.reference}: deadline extended",
        metadata={"extended_due_at": case.extended_due_at.isoformat(), "note": note},
        request=request,
    )
    return case
