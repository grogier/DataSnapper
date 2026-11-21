from __future__ import annotations

import json
from hashlib import sha256

from django.db import transaction
from django.utils import timezone

from audit.models import AuditLog
from core.utils import get_client_ip


def _payload(
    prev_hash: str,
    action: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    metadata: dict,
    created_at,
) -> str:
    return json.dumps(
        {
            "prev": prev_hash,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "summary": summary,
            "metadata": metadata or {},
            "created_at": created_at.isoformat(),
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def log(
    *,
    actor=None,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    summary: str = "",
    metadata: dict | None = None,
    request=None,
) -> AuditLog:
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    metadata = metadata or {}
    created_at = timezone.now()

    with transaction.atomic():
        previous = AuditLog.objects.order_by("-id").first()
        prev_hash = previous.entry_hash if previous else AuditLog.GENESIS_HASH
        payload = _payload(prev_hash, action, entity_type, entity_id, summary, metadata, created_at)
        entry_hash = sha256(payload.encode("utf-8")).hexdigest()
        return AuditLog.objects.create(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else "",
            summary=summary[:255],
            metadata=metadata,
            ip=get_client_ip(request) if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""),
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=created_at,
        )


def verify_chain() -> tuple[bool, int | None]:
    previous_hash = AuditLog.GENESIS_HASH
    for entry in AuditLog.objects.order_by("id").iterator():
        payload = _payload(
            previous_hash,
            entry.action,
            entry.entity_type,
            entry.entity_id,
            entry.summary,
            entry.metadata,
            entry.created_at,
        )
        expected = sha256(payload.encode("utf-8")).hexdigest()
        if entry.prev_hash != previous_hash or entry.entry_hash != expected:
            return False, entry.pk
        previous_hash = entry.entry_hash
    return True, None
