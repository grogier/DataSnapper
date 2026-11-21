from email import message_from_bytes, policy

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from cases.models import Case
from cases.services import transition_case
from correspondence.models import Attachment, Message, Template
from correspondence.services import (
    create_draft_message,
    generate_eml,
    log_reply,
    pdf_available,
    render_message_pdf,
    send_message,
    store_attachment,
)


@pytest.mark.django_db
def test_compose_save_and_send_flow(client_logged_in, case, profile, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    response = client_logged_in.post(
        reverse("case-compose", args=[case.pk]),
        {
            "template": template.pk,
            "to_address": "privacy@example.com",
            "scope": "All data linked to me@example.com.",
            "extra_note": "Please also confirm whether my data is sold.",
            "action": "save",
        },
    )
    assert response.status_code == 302
    message = Message.objects.get(case=case)
    assert message.status == Message.Status.DRAFT
    assert "me@example.com" in message.body
    assert "Please also confirm whether my data is sold." in message.body

    response = client_logged_in.post(
        reverse("message-send", args=[case.pk, message.pk]),
        {"send_method": Message.SendMethod.MANUAL_EXPORT},
    )
    assert response.status_code == 302
    message.refresh_from_db()
    case.refresh_from_db()
    assert message.status == Message.Status.SENT
    assert message.sent_at is not None
    assert message.message_id
    assert case.status == Case.Status.SENT
    assert case.sent_at is not None
    assert case.due_at is not None


@pytest.mark.django_db
def test_reply_is_logged_and_case_acknowledged(case, user):
    transition_case(case, Case.Status.SENT, actor=user)
    message = log_reply(
        case,
        channel=Message.Channel.EMAIL,
        from_address="privacy@example.com",
        subject="We received your request",
        body="We will respond shortly.",
        received_at=timezone.now(),
        mark_acknowledged=True,
        actor=user,
    )
    case.refresh_from_db()
    assert message.direction == Message.Direction.INBOUND
    assert message.status == Message.Status.RECEIVED
    assert case.status == Case.Status.ACKNOWLEDGED


@pytest.mark.django_db
def test_identity_attachment_is_encrypted_and_downloadable(client_logged_in, case, user):
    upload = SimpleUploadedFile("passport.txt", b"my-secret-id", content_type="text/plain")
    attachment = store_attachment(
        uploaded_file=upload, kind=Attachment.Kind.IDENTITY, case=case, actor=user
    )
    assert attachment.file.name in (None, "")
    assert attachment.encrypted_file.name
    assert attachment.size == len(b"my-secret-id")

    response = client_logged_in.get(reverse("attachment-download", args=[attachment.pk]))
    assert response.status_code == 200
    assert response.content == b"my-secret-id"


@pytest.mark.django_db
def test_normal_attachment_is_stored_plain(case, user):
    upload = SimpleUploadedFile("proof.eml", b"Subject: test", content_type="message/rfc822")
    attachment = store_attachment(
        uploaded_file=upload, kind=Attachment.Kind.PROOF_OF_SENDING, case=case, actor=user
    )
    assert attachment.file.name
    assert not attachment.encrypted_file
    assert attachment.sha256


@pytest.mark.django_db
def test_eml_export_contains_headers(case, profile, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    message = create_draft_message(case, template)
    send_message(message)
    message.refresh_from_db()
    raw = generate_eml(message)
    parsed = message_from_bytes(raw, policy=policy.default)
    assert parsed["Subject"] == message.subject
    assert parsed["To"] == "privacy@example.com"
    assert parsed["X-DataSnapper-Case"] == case.reference
    assert "Yours faithfully" in parsed.get_payload()


@pytest.mark.django_db
def test_pdf_export(case, profile, templates):
    if not pdf_available():
        pytest.skip("WeasyPrint not available")
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    message = create_draft_message(case, template)
    pdf = render_message_pdf(message)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


@pytest.mark.django_db
def test_compose_page_requires_profile(client_logged_in, case, templates):
    response = client_logged_in.get(reverse("case-compose", args=[case.pk]))
    assert response.status_code == 302
    assert response.url == reverse("settings")
