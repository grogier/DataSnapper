from __future__ import annotations

import mimetypes
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone

from audit.services import log
from cases.models import Case, CaseEvent
from cases.services import add_event, transition_case
from companies.models import Organization
from core.models import DataSubject
from core.utils import (
    add_months,
    encrypt_bytes,
    format_date,
    missing_variables,
    safe_filename,
    sha256_bytes,
)
from correspondence.models import Attachment, Message, Template

SCOPE_FALLBACK = {
    "en": "all personal data you process about me",
    "nl": "alle persoonsgegevens die u over mij verwerkt",
}


def build_letter_context(
    case: Case,
    template: Template,
    *,
    scope: str | None = None,
    extra_note: str = "",
) -> dict:
    profile = DataSubject.get_primary()
    organization = case.organization
    contact = organization.primary_contact
    locale = template.locale
    scope_text = (scope or case.scope or "").strip() or SCOPE_FALLBACK.get(
        locale, SCOPE_FALLBACK["en"]
    )

    profile_data = {
        "full_name": profile.full_name if profile else "",
        "email": profile.email if profile else "",
        "phone": profile.phone if profile else "",
        "postal_address": profile.postal_address if profile else "",
        "country": profile.country if profile else "",
    }
    organization_data = {
        "name": organization.name,
        "legal_name": organization.display_name,
        "postal_address": organization.postal_address,
        "privacy_email": organization.privacy_email,
        "dpo_email": organization.dpo_email,
        "best_email": organization.best_email,
        "website": organization.website,
        "country": organization.country,
    }
    contact_data = {
        "name": contact.name if contact else "",
        "email": contact.email if contact else "",
        "role": contact.get_role_display() if contact else "",
    }
    due = case.effective_due
    return {
        "profile": profile_data,
        "organization": organization_data,
        "contact": contact_data,
        "case": {
            "reference": case.reference,
            "right": case.right,
            "right_label": case.right_label,
            "scope": case.scope,
            "scope_text": scope_text,
            "jurisdiction": case.jurisdiction,
            "opened_at": format_date(case.opened_at, locale),
            "sent_at": format_date(case.sent_at, locale),
            "due_date": format_date(due, locale),
            "status": case.get_status_display(),
        },
        "today": format_date(timezone.localdate(), locale),
        "today_iso": timezone.localdate().isoformat(),
        "due_date": format_date(due, locale),
        "signature": profile_data["full_name"],
        "extra_note": extra_note.strip(),
        "locale": locale,
    }


def create_draft_message(
    case: Case,
    template: Template,
    *,
    scope: str = "",
    extra_note: str = "",
    to_address: str = "",
    subject_override: str = "",
    body_override: str = "",
    actor=None,
    request=None,
) -> Message:
    context = build_letter_context(case, template, scope=scope, extra_note=extra_note)
    subject, body = template.render(context)
    if subject_override.strip():
        subject = subject_override.strip()
    if body_override.strip():
        body = body_override.strip()

    profile = DataSubject.get_primary()
    message = Message.objects.create(
        case=case,
        direction=Message.Direction.OUTBOUND,
        channel=Message.Channel.EMAIL,
        status=Message.Status.DRAFT,
        from_address=profile.email if profile else "",
        to_address=to_address.strip() or case.organization.best_email,
        subject=subject,
        body=body,
        template=template,
        template_version=template.version,
    )
    add_event(
        case,
        CaseEvent.EventType.MESSAGE,
        actor=actor,
        summary=f"Draft prepared: {subject}",
        metadata={"message_id": message.pk},
    )
    log(
        actor=actor,
        action="message.draft",
        entity_type="message",
        entity_id=str(message.pk),
        summary=f"{case.reference}: draft prepared",
        metadata={"template": template.slug, "locale": template.locale},
        request=request,
    )
    return message


def send_message(
    message: Message,
    *,
    actor=None,
    request=None,
    send_method: str = Message.SendMethod.MANUAL_EXPORT,
) -> Message:
    if message.status != Message.Status.DRAFT:
        raise ValueError("Only draft messages can be marked as sent.")
    case = message.case
    now = timezone.now()
    message.status = Message.Status.SENT
    message.sent_at = now
    message.send_method = send_method
    if not message.message_id:
        message.message_id = make_msgid(domain="datasnapper.local")
    message.save()

    if case.status in {Case.Status.DRAFT, Case.Status.QUEUED}:
        transition_case(
            case,
            Case.Status.SENT,
            actor=actor,
            note=f"Sent: {message.subject}",
            request=request,
        )
    else:
        if not case.sent_at:
            case.sent_at = timezone.localdate()
            case.due_at = add_months(case.sent_at, 1)
            case.save()
        add_event(
            case,
            CaseEvent.EventType.MESSAGE,
            actor=actor,
            summary=f"Message marked sent: {message.subject}",
            metadata={"message_id": message.pk},
        )
    log(
        actor=actor,
        action="message.send",
        entity_type="message",
        entity_id=str(message.pk),
        summary=f"{case.reference}: message marked sent",
        metadata={"send_method": send_method, "subject": message.subject},
        request=request,
    )
    return message


def log_reply(
    case: Case,
    *,
    channel: str,
    from_address: str,
    subject: str,
    body: str,
    received_at: datetime,
    notes: str = "",
    mark_acknowledged: bool = False,
    actor=None,
    request=None,
) -> Message:
    profile = DataSubject.get_primary()
    message = Message.objects.create(
        case=case,
        direction=Message.Direction.INBOUND,
        channel=channel,
        status=Message.Status.RECEIVED,
        from_address=from_address,
        to_address=profile.email if profile else "",
        subject=subject,
        body=body,
        received_at=received_at,
        notes=notes,
    )
    add_event(
        case,
        CaseEvent.EventType.REPLY,
        actor=actor,
        summary=f"Reply logged: {subject}",
        metadata={"message_id": message.pk},
    )
    if mark_acknowledged and Case.Status.ACKNOWLEDGED in [
        value for value, _ in case.allowed_transitions()
    ]:
        transition_case(
            case,
            Case.Status.ACKNOWLEDGED,
            actor=actor,
            note="Marked acknowledged when logging the reply.",
            request=request,
        )
    log(
        actor=actor,
        action="message.reply",
        entity_type="message",
        entity_id=str(message.pk),
        summary=f"{case.reference}: reply logged",
        metadata={"channel": channel, "subject": subject},
        request=request,
    )
    return message


def store_attachment(
    *,
    uploaded_file,
    kind: str,
    case: Case | None = None,
    message: Message | None = None,
    organization: Organization | None = None,
    notes: str = "",
    actor=None,
    request=None,
) -> Attachment:
    data = uploaded_file.read()
    max_size = settings.FILE_UPLOAD_MAX_MEMORY_SIZE
    if len(data) > max_size:
        raise ValueError(f"File is larger than the {max_size // (1024 * 1024)} MB limit.")
    if not data:
        raise ValueError("The uploaded file is empty.")

    name = safe_filename(uploaded_file.name)
    mime = (
        getattr(uploaded_file, "content_type", "")
        or mimetypes.guess_type(name)[0]
        or "application/octet-stream"
    )
    attachment = Attachment(
        case=case,
        message=message,
        organization=organization or (case.organization if case else None),
        kind=kind,
        original_name=name,
        mime=mime,
        size=len(data),
        sha256=sha256_bytes(data),
        notes=notes,
        uploaded_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    if kind == Attachment.Kind.IDENTITY:
        encrypted = encrypt_bytes(data)
        attachment.encrypted_file.save(f"{uuid4().hex}.enc", ContentFile(encrypted), save=False)
    else:
        attachment.file.save(f"{uuid4().hex}-{name}", ContentFile(data), save=False)
    attachment.save()

    if case:
        add_event(
            case,
            CaseEvent.EventType.ATTACHMENT,
            actor=actor,
            summary=f"Document added: {name}",
            metadata={"attachment_id": attachment.pk, "kind": kind},
        )
    log(
        actor=actor,
        action="attachment.create",
        entity_type="attachment",
        entity_id=str(attachment.pk),
        summary=f"Added document {name}",
        metadata={"kind": kind, "size": len(data), "sha256": attachment.sha256},
        request=request,
    )
    return attachment


def generate_eml(message: Message) -> bytes:
    profile = DataSubject.get_primary()
    email = EmailMessage()
    email["From"] = message.from_address or (profile.email if profile else "me@localhost")
    email["To"] = message.to_address or message.case.organization.best_email
    email["Subject"] = message.subject
    email["Date"] = format_datetime(message.sent_at or timezone.now())
    email["Message-ID"] = message.message_id or make_msgid(domain="datasnapper.local")
    email["X-DataSnapper-Case"] = message.case.reference
    if message.in_reply_to:
        email["In-Reply-To"] = message.in_reply_to
    email.set_content(message.body)
    return email.as_bytes()


def pdf_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except Exception:
        return False
    return True


def render_message_pdf(message: Message) -> bytes:
    profile = DataSubject.get_primary()
    organization = message.case.organization
    contact = organization.primary_contact
    html = render_to_string(
        "pdf/letter.html",
        {
            "message": message,
            "case": message.case,
            "profile": profile,
            "organization": organization,
            "contact": contact,
            "today": timezone.localdate(),
        },
    )
    try:
        from weasyprint import HTML
    except Exception as exc:
        raise RuntimeError("PDF rendering is not available on this server.") from exc
    return HTML(string=html).write_pdf()


def missing_for_template(template: Template, context: dict) -> list[str]:
    return missing_variables([template.subject, template.body], context)
