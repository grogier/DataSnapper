from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from audit.services import log
from cases.models import Case
from cases.rights import RIGHT_CHOICES
from core.models import DataSubject
from core.utils import decrypt_bytes
from correspondence.forms import (
    AttachmentForm,
    ComposeForm,
    EvidenceUploadForm,
    ReplyForm,
    TemplateForm,
)
from correspondence.models import Attachment, Message, Template
from correspondence.services import (
    build_letter_context,
    create_draft_message,
    generate_eml,
    log_reply,
    missing_for_template,
    pdf_available,
    render_message_pdf,
    send_message,
    store_attachment,
)


@login_required
def template_list(request):
    templates = Template.objects.all()
    query = request.GET.get("q", "").strip()
    right = request.GET.get("right", "")
    locale = request.GET.get("locale", "")
    active = request.GET.get("active", "")
    if query:
        templates = templates.filter(Q(name__icontains=query) | Q(slug__icontains=query))
    if right:
        templates = templates.filter(right=right)
    if locale:
        templates = templates.filter(locale=locale)
    if active in {"0", "1"}:
        templates = templates.filter(is_active=active == "1")

    paginator = Paginator(templates, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "correspondence/template_list.html",
        {
            "page": page,
            "templates": page.object_list,
            "query": query,
            "right": right,
            "locale": locale,
            "active": active,
            "total": paginator.count,
            "rights": RIGHT_CHOICES,
        },
    )


@login_required
def template_detail(request, pk):
    template = get_object_or_404(Template, pk=pk)
    versions = Template.objects.filter(slug=template.slug, locale=template.locale).order_by(
        "-version"
    )
    return render(
        request,
        "correspondence/template_detail.html",
        {"template": template, "versions": versions},
    )


@login_required
def template_create(request):
    form = TemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        template = form.save(commit=False)
        template.version = 1
        template.is_active = True
        if Template.objects.filter(slug=template.slug, locale=template.locale).exists():
            form.add_error("slug", "A template with this slug and language already exists.")
        else:
            template.save()
            log(
                actor=request.user,
                action="template.create",
                entity_type="template",
                entity_id=str(template.pk),
                summary=f"Created template {template.name}",
                request=request,
            )
            messages.success(request, "Template created.")
            return redirect(template)
    return render(
        request,
        "correspondence/template_form.html",
        {"form": form, "title": "New template", "template": None},
    )


@login_required
def template_edit(request, pk):
    template = get_object_or_404(Template, pk=pk)
    form = TemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        cleaned = form.cleaned_data
        locale = cleaned["locale"]
        highest = (
            Template.objects.filter(slug=template.slug, locale=locale).aggregate(
                value=Max("version")
            )["value"]
            or 0
        )
        Template.objects.filter(slug=template.slug, locale=locale).update(is_active=False)
        new_version = Template.objects.create(
            slug=template.slug,
            name=cleaned["name"],
            right=cleaned["right"],
            jurisdiction=cleaned["jurisdiction"],
            locale=locale,
            subject=cleaned["subject"],
            body=cleaned["body"],
            version=highest + 1,
            is_active=True,
            legal_refs=cleaned["legal_refs"],
            notes=cleaned["notes"],
        )
        log(
            actor=request.user,
            action="template.version",
            entity_type="template",
            entity_id=str(new_version.pk),
            summary=f"Created version {new_version.version} of {new_version.name}",
            request=request,
        )
        messages.success(request, f"Saved as version {new_version.version}.")
        return redirect(new_version)
    return render(
        request,
        "correspondence/template_form.html",
        {"form": form, "title": f"Edit {template.name}", "template": template},
    )


@login_required
def compose(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    profile = DataSubject.get_primary()
    if profile is None:
        messages.warning(request, "Add your own profile in Settings before composing a letter.")
        return redirect("settings")
    if not Template.objects.filter(right=case.right, is_active=True).exists():
        messages.warning(request, "No active template exists for this request type. Add one first.")
        return redirect(case)

    form = ComposeForm(request.POST or None, case=case)
    preview = None
    action = request.POST.get("action", "")

    if request.method == "POST" and form.is_valid():
        template = form.cleaned_data["template"]
        context = build_letter_context(
            case,
            template,
            scope=form.cleaned_data["scope"],
            extra_note=form.cleaned_data["extra_note"],
        )
        missing = missing_for_template(template, context)
        if action == "save":
            message = create_draft_message(
                case,
                template,
                scope=form.cleaned_data["scope"],
                extra_note=form.cleaned_data["extra_note"],
                to_address=form.cleaned_data["to_address"],
                actor=request.user,
                request=request,
            )
            messages.success(request, "Draft saved. Review it, then export or mark it as sent.")
            return redirect("message-detail", pk=case.pk, message_pk=message.pk)
        subject, body = template.render(context)
        preview = {
            "template": template,
            "subject": subject,
            "body": body,
            "missing": missing,
        }

    return render(
        request,
        "cases/compose.html",
        {
            "case": case,
            "form": form,
            "preview": preview,
            "profile": profile,
            "pdf_available": pdf_available(),
        },
    )


@login_required
def message_detail(request, pk, message_pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    message = get_object_or_404(
        Message.objects.select_related("template"), pk=message_pk, case=case
    )
    return render(
        request,
        "correspondence/message_detail.html",
        {
            "case": case,
            "message": message,
            "attachments": message.attachments.all(),
            "pdf_available": pdf_available(),
            "send_methods": Message.SendMethod.choices,
        },
    )


@login_required
@require_POST
def message_send(request, pk, message_pk):
    message = get_object_or_404(Message, pk=message_pk, case__pk=pk)
    if not message.is_draft:
        messages.error(request, "Only draft messages can be marked as sent.")
        return redirect("message-detail", pk=pk, message_pk=message.pk)
    send_method = request.POST.get("send_method", Message.SendMethod.MANUAL_EXPORT)
    valid_methods = {value for value, _ in Message.SendMethod.choices}
    if send_method not in valid_methods:
        send_method = Message.SendMethod.MANUAL_EXPORT
    try:
        send_message(message, actor=request.user, request=request, send_method=send_method)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Message marked as sent and the deadline was updated.")
    return redirect("message-detail", pk=pk, message_pk=message.pk)


@login_required
def message_pdf(request, pk, message_pk):
    message = get_object_or_404(Message, pk=message_pk, case__pk=pk)
    try:
        content = render_message_pdf(message)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("message-print", pk=pk, message_pk=message.pk)
    log(
        actor=request.user,
        action="message.export_pdf",
        entity_type="message",
        entity_id=str(message.pk),
        summary=f"Exported {message.case.reference} as PDF",
        request=request,
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        True, f"{message.case.reference}-{message.pk}.pdf"
    )
    return response


@login_required
def message_eml(request, pk, message_pk):
    message = get_object_or_404(Message, pk=message_pk, case__pk=pk)
    content = generate_eml(message)
    log(
        actor=request.user,
        action="message.export_eml",
        entity_type="message",
        entity_id=str(message.pk),
        summary=f"Exported {message.case.reference} as .eml",
        request=request,
    )
    response = HttpResponse(content, content_type="message/rfc822")
    response["Content-Disposition"] = content_disposition_header(
        True, f"{message.case.reference}-{message.pk}.eml"
    )
    return response


@login_required
def message_print(request, pk, message_pk):
    message = get_object_or_404(Message, pk=message_pk, case__pk=pk)
    return render(
        request,
        "correspondence/message_print.html",
        {
            "message": message,
            "case": message.case,
            "profile": DataSubject.get_primary(),
            "organization": message.case.organization,
            "contact": message.case.organization.primary_contact,
            "today": timezone.localdate(),
        },
    )


@login_required
@require_POST
def message_delete(request, pk, message_pk):
    message = get_object_or_404(Message, pk=message_pk, case__pk=pk)
    if not message.is_draft:
        messages.error(request, "Only drafts can be deleted. Keep sent messages in the file.")
        return redirect("message-detail", pk=pk, message_pk=message.pk)
    message.delete()
    log(
        actor=request.user,
        action="message.delete_draft",
        entity_type="message",
        entity_id=str(message_pk),
        summary=f"Deleted a draft on {pk}",
        request=request,
    )
    messages.success(request, "Draft deleted.")
    return redirect("case-detail", pk=pk)


@login_required
def reply(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    initial = {
        "received_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        "from_address": case.organization.best_email,
        "subject": f"Re: {case.right_label} — {case.reference}",
    }
    form = ReplyForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        log_reply(
            case,
            channel=form.cleaned_data["channel"],
            from_address=form.cleaned_data["from_address"],
            subject=form.cleaned_data["subject"],
            body=form.cleaned_data["body"],
            received_at=form.cleaned_data["received_at"],
            notes=form.cleaned_data["notes"],
            mark_acknowledged=form.cleaned_data["mark_acknowledged"],
            actor=request.user,
            request=request,
        )
        messages.success(request, "Reply logged.")
        return redirect(case)
    return render(request, "correspondence/reply_form.html", {"case": case, "form": form})


@login_required
@require_POST
def attachment_upload(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            store_attachment(
                uploaded_file=form.cleaned_data["file"],
                kind=form.cleaned_data["kind"],
                case=case,
                notes=form.cleaned_data["notes"],
                actor=request.user,
                request=request,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Document added.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect(case)


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk)
    if attachment.encrypted_file:
        try:
            data = decrypt_bytes(attachment.encrypted_file.read())
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("evidence-list")
        response = HttpResponse(data, content_type=attachment.mime or "application/octet-stream")
    else:
        if not attachment.file:
            messages.error(request, "This document has no file attached.")
            return redirect("evidence-list")
        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_name,
        )
    response["Content-Disposition"] = content_disposition_header(True, attachment.original_name)
    if attachment.kind == Attachment.Kind.IDENTITY:
        log(
            actor=request.user,
            action="attachment.download_identity",
            entity_type="attachment",
            entity_id=str(attachment.pk),
            summary=f"Downloaded identity document {attachment.original_name}",
            request=request,
        )
    return response


@login_required
@require_POST
def attachment_delete(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk)
    case = attachment.case
    name = attachment.original_name
    if attachment.file:
        attachment.file.delete(save=False)
    if attachment.encrypted_file:
        attachment.encrypted_file.delete(save=False)
    attachment.delete()
    log(
        actor=request.user,
        action="attachment.delete",
        entity_type="attachment",
        entity_id=str(pk),
        summary=f"Deleted document {name}",
        request=request,
    )
    messages.success(request, "Document deleted.")
    if case:
        return redirect(case)
    return redirect("evidence-list")


@login_required
def evidence_list(request):
    attachments = Attachment.objects.select_related("case", "organization", "message")
    kind = request.GET.get("kind", "")
    query = request.GET.get("q", "").strip()
    if kind:
        attachments = attachments.filter(kind=kind)
    if query:
        attachments = attachments.filter(
            Q(original_name__icontains=query)
            | Q(notes__icontains=query)
            | Q(case__reference__icontains=query)
            | Q(organization__name__icontains=query)
        )
    paginator = Paginator(attachments, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "correspondence/evidence_list.html",
        {
            "page": page,
            "attachments": page.object_list,
            "kind": kind,
            "query": query,
            "kinds": Attachment.Kind.choices,
            "total": paginator.count,
        },
    )


@login_required
def evidence_upload(request):
    form = EvidenceUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            attachment = store_attachment(
                uploaded_file=form.cleaned_data["file"],
                kind=form.cleaned_data["kind"],
                case=form.cleaned_data["case"],
                notes=form.cleaned_data["notes"],
                actor=request.user,
                request=request,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Document added to the evidence vault.")
            if attachment.case:
                return redirect(attachment.case)
            return redirect("evidence-list")
    return render(
        request,
        "correspondence/evidence_form.html",
        {"form": form},
    )
