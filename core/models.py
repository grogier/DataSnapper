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

    class LLMProvider(models.TextChoices):
        OLLAMA = "ollama", "Ollama (local)"
        OPENAI = "openai", "OpenAI-compatible"
        DEEPSEEK = "deepseek", "DeepSeek (cloud)"

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
    llm_enabled = models.BooleanField(
        default=False,
        help_text="Enable AI assistance for drafting requests. Nothing is sent until this is on.",
    )
    llm_provider = models.CharField(
        max_length=20,
        choices=LLMProvider.choices,
        default=LLMProvider.OLLAMA,
    )
    llm_base_url = models.CharField(
        max_length=255,
        default="http://localhost:11434",
        help_text="For Docker, use http://host.docker.internal:11434 or http://ollama:11434.",
    )
    llm_model = models.CharField(
        max_length=120,
        default="llama3.1:8b",
        help_text="Model name understood by the chosen provider.",
    )
    llm_timeout = models.PositiveIntegerField(
        default=120,
        help_text="Seconds to wait for the LLM. Local models can be slow.",
    )
    llm_max_output_tokens = models.PositiveIntegerField(
        default=1500,
        help_text="Upper bound for generated tokens.",
    )
    llm_reasoning = models.BooleanField(
        default=False,
        help_text="Use thinking mode where the provider supports it. Slower, better for complex scope.",
    )
    llm_share_personal_data = models.BooleanField(
        default=False,
        help_text="Send your name, address and contact details to the LLM. Off keeps placeholders.",
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

    @property
    def llm_is_cloud(self) -> bool:
        from core.llm.providers import endpoint_is_local

        return not endpoint_is_local(self.llm_base_url)
