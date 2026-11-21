from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse

from cases.models import Case
from cases.rights import RIGHT_CHOICES
from core.models import TimeStampedModel
from core.utils import render_text, template_variables


class Template(TimeStampedModel):
    class Locale(models.TextChoices):
        EN = "en", "English"
        NL = "nl", "Nederlands"

    slug = models.SlugField(max_length=80)
    name = models.CharField(max_length=200)
    right = models.CharField(max_length=40, choices=RIGHT_CHOICES)
    jurisdiction = models.CharField(max_length=40, default="EU")
    locale = models.CharField(max_length=5, choices=Locale.choices, default=Locale.EN)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    legal_refs = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["right", "locale", "slug", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "locale", "version"], name="unique_template_version"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.locale.upper()} v{self.version})"

    def get_absolute_url(self) -> str:
        return reverse("template-detail", args=[self.pk])

    def render(self, context: dict) -> tuple[str, str]:
        subject = render_text(self.subject, context, autoescape=False).strip()
        body = render_text(self.body, context, autoescape=False).strip()
        return subject, body

    @property
    def variables(self) -> list[str]:
        return template_variables(self.subject, self.body)


class Message(TimeStampedModel):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", "Outbound"
        INBOUND = "inbound", "Inbound"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WEB_FORM = "web_form", "Web form"
        POST = "post", "Post"
        PHONE = "phone", "Phone"
        PORTAL = "portal", "Online portal"
        OTHER = "other", "Other"

    class SendMethod(models.TextChoices):
        MANUAL_EXPORT = "manual_export", "Exported and sent manually"
        WEB_FORM = "web_form", "Submitted through web form"
        POST = "post", "Sent by post"
        SMTP = "smtp", "Sent via SMTP"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        RECEIVED = "received", "Received"
        LOGGED = "logged", "Logged"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(
        max_length=10, choices=Direction.choices, default=Direction.OUTBOUND
    )
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.EMAIL)
    send_method = models.CharField(max_length=20, choices=SendMethod.choices, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    from_address = models.CharField(max_length=320, blank=True)
    to_address = models.CharField(max_length=320, blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    template = models.ForeignKey(
        Template, null=True, blank=True, on_delete=models.SET_NULL, related_name="messages"
    )
    template_version = models.PositiveIntegerField(null=True, blank=True)
    message_id = models.CharField(max_length=255, blank=True)
    in_reply_to = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    ai_generated = models.BooleanField(default=False)
    ai_provider = models.CharField(max_length=40, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.get_direction_display()}: {self.subject}"

    @property
    def is_draft(self) -> bool:
        return self.status == self.Status.DRAFT

    @property
    def source_label(self) -> str:
        """Say plainly where the letter text came from."""
        if self.ai_generated:
            return "AI-generated"
        if self.template_id:
            return "From template"
        return "Free text"

    @property
    def source_detail(self) -> str:
        if self.ai_generated:
            return " · ".join(value for value in (self.ai_provider, self.ai_model) if value)
        if self.template_id and self.template:
            version = f" v{self.template_version}" if self.template_version else ""
            return f"{self.template.name}{version}"
        return ""


class Attachment(TimeStampedModel):
    class Kind(models.TextChoices):
        IDENTITY = "identity", "Identity document"
        PROOF_OF_SENDING = "proof_of_sending", "Proof of sending"
        COMPANY_RESPONSE = "company_response", "Company response"
        CORRESPONDENCE = "correspondence", "Correspondence"
        OTHER = "other", "Other"

    case = models.ForeignKey(
        Case, null=True, blank=True, on_delete=models.CASCADE, related_name="attachments"
    )
    message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attachments",
    )
    organization = models.ForeignKey(
        "companies.Organization",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    kind = models.CharField(max_length=30, choices=Kind.choices, default=Kind.OTHER)
    file = models.FileField(upload_to="attachments/%Y/%m/", null=True, blank=True)
    encrypted_file = models.FileField(upload_to="identity/%Y/%m/", null=True, blank=True)
    original_name = models.CharField(max_length=255)
    mime = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.original_name

    @property
    def is_encrypted(self) -> bool:
        return bool(self.encrypted_file)

    def get_absolute_url(self) -> str:
        return reverse("attachment-download", args=[self.pk])
