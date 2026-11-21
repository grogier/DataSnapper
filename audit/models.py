from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    """Append-only, hash-chained record of meaningful actions."""

    GENESIS_HASH = "0" * 64

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_entries",
    )
    action = models.CharField(max_length=100, db_index=True)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=60, blank=True)
    summary = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    prev_hash = models.CharField(max_length=64)
    entry_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "audit entry"
        verbose_name_plural = "audit log"

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}: {self.summary}"
