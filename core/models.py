from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DataSubject(TimeStampedModel):
    """The person whose rights are being exercised."""

    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    postal_address = models.TextField(
        blank=True, help_text="Full postal address, one line per address line."
    )
    country = models.CharField(max_length=100, blank=True, default="Netherlands")
    is_primary = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "data subject"
        verbose_name_plural = "data subjects"

    def __str__(self) -> str:
        return self.full_name

    @classmethod
    def get_primary(cls) -> DataSubject | None:
        return cls.objects.filter(is_primary=True).first() or cls.objects.first()

    @property
    def address_lines(self) -> list[str]:
        return [line for line in self.postal_address.splitlines() if line.strip()]


class AppSettings(TimeStampedModel):
    """Singleton row with application-wide preferences."""

    case_prefix = models.CharField(
        max_length=12,
        default="DSAR",
        help_text="Prefix for case references, e.g. DSAR-2026-0001.",
    )
    default_locale = models.CharField(
        max_length=5,
        choices=[("en", "English"), ("nl", "Nederlands")],
        default="en",
    )
    reminder_days = models.CharField(
        max_length=40,
        default="10,3,0",
        help_text="Comma separated reminder offsets in days before the deadline.",
    )
    retention_days = models.PositiveIntegerField(
        default=0,
        help_text="0 keeps case files indefinitely. Otherwise used by the purge command.",
    )

    class Meta:
        verbose_name = "application settings"
        verbose_name_plural = "application settings"

    def __str__(self) -> str:
        return "Application settings"

    @classmethod
    def load(cls) -> AppSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def reminder_offsets(self) -> list[int]:
        offsets: list[int] = []
        for part in self.reminder_days.split(","):
            part = part.strip()
            if part.isdigit():
                offsets.append(int(part))
        return sorted(set(offsets), reverse=True)
