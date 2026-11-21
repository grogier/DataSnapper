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
from core import llm
from core.models import AppSettings, DataSubject
from core.utils import decrypt_bytes
from correspondence import assist
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

    llm_settings = assist.ai_context(case)
    ai_templates = Template.objects.filter(right=case.right, is_active=True)
    has_templates = ai_templates.exists()
    if not has_templates and not llm_settings["enabled"]:
        messages.warning(request, "No active template exists for this request type. Add one first.")
        return redirect(case)

    form = ComposeForm(
        request.POST or None,
        case=case,
        include_ai_options=llm_settings["enabled"],
    )
    preview = None
    action = request.POST.get("action", "")

    if request.method == "POST" and form.is_valid() and action in {"preview", "save"}:
        template = form.cleaned_data["template"]
        if template is None:
            form.add_error("template", "Choose a template, or generate the letter with AI.")
        else:
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
                    subject_override=request.POST.get("subject", ""),
                    body_override=request.POST.get("body", ""),
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
                "to_address": form.cleaned_data["to_address"] or case.organization.best_email,
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
            "llm": llm_settings,
            "has_templates": has_templates,
            "checklist_items": case.checklist_items,
        },
    )


def _selected_ai_template(case: Case, request) -> Template | None:
    template_id = request.POST.get("template", "")
    if not template_id:
        return None
    try:
        return Template.objects.filter(pk=template_id, right=case.right, is_active=True).first()
    except (TypeError, ValueError):
        return None


def _ai_inputs(request, case: Case) -> tuple[dict | None, str]:
    mode = request.POST.get("mode", "draft")
    if mode not in assist.MODES:
        mode = "draft"
    template = _selected_ai_template(case, request)
    locale = template.locale if template else AppSettings.load().default_locale
    tone = request.POST.get("tone", "neutral")
    if tone not in {"neutral", "firm"}:
        tone = "neutral"
    length = request.POST.get("length", "concise")
    if length not in {"concise", "thorough"}:
        length = "concise"

    existing_subject = request.POST.get("existing_subject", "")
    existing_body = request.POST.get("existing_body", "")
    message_pk = request.POST.get("message_pk", "")
    if mode == "rewrite":
        if message_pk:
            try:
                message = Message.objects.filter(pk=message_pk, case=case).first()
            except (TypeError, ValueError):
                message = None
            if message is None:
                return None, "That message does not belong to this case."
            if not llm.resolve_config().share_personal_data:
                return None, (
                    "Enable 'Share personal data with the LLM' in Settings before rewriting "
                    "a rendered message. A template body with placeholders is safe to rewrite."
                )
            existing_subject = message.subject
            existing_body = message.body
        elif not existing_body.strip() and template is not None:
            existing_subject = template.subject
            existing_body = template.body
        if not existing_body.strip():
            return None, "Paste the text you want to rewrite, or choose a template."

    return (
        {
            "mode": mode,
            "template": template,
            "locale": locale,
            "tone": tone,
            "length": length,
            "scope": request.POST.get("scope", ""),
            "instructions": request.POST.get("instructions") or request.POST.get("extra_note", ""),
            "checklist_keys": request.POST.getlist("checklist"),
            "existing_subject": existing_subject,
            "existing_body": existing_body,
            "reasoning": bool(request.POST.get("reasoning")),
        },
        "",
    )


@login_required
@require_POST
def case_ai_generate(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    context = assist.ai_context(case)
    if not context["enabled"]:
        return render(
            request,
            "correspondence/_ai_result.html",
            {
                "case": case,
                "error": "AI assistance is disabled. Enable it in Settings first.",
                "llm": context,
            },
        )
    inputs, error = _ai_inputs(request, case)
    if error:
        return render(
            request,
            "correspondence/_ai_result.html",
            {"case": case, "error": error, "llm": assist.ai_context(case)},
        )
    template = inputs.pop("template")
    try:
        assist_result, llm_result, _bundle = assist.generate_assist(
            case,
            actor=request.user,
            request=request,
            template=template,
            **inputs,
        )
    except llm.LLMError as exc:
        return render(
            request,
            "correspondence/_ai_result.html",
            {
                "case": case,
                "error": str(exc),
                "mode": inputs["mode"],
                "llm": assist.ai_context(case),
            },
        )
    return render(
        request,
        "correspondence/_ai_result.html",
        {
            "case": case,
            "result": assist_result,
            "meta": llm_result,
            "mode": inputs["mode"],
            "template": template,
            "to_address": request.POST.get("to_address", ""),
            "llm": assist.ai_context(case),
        },
    )


@login_required
@require_POST
def case_ai_prompt(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    inputs, error = _ai_inputs(request, case)
    if error:
        return render(
            request,
            "correspondence/_ai_prompt.html",
            {"case": case, "error": error, "llm": assist.ai_context(case)},
        )
    bundle = assist.build_prompt(
        case,
        mode=inputs["mode"],
        locale=inputs["locale"],
        tone=inputs["tone"],
        length=inputs["length"],
        scope=inputs["scope"],
        instructions=inputs["instructions"],
        checklist_keys=inputs["checklist_keys"],
        include_personal=llm.resolve_config().share_personal_data,
        existing_subject=inputs["existing_subject"],
        existing_body=inputs["existing_body"],
        template_subject=inputs["template"].subject if inputs["template"] else "",
        template_body=inputs["template"].body if inputs["template"] else "",
    )
    return render(
        request,
        "correspondence/_ai_prompt.html",
        {"case": case, "bundle": bundle, "llm": assist.ai_context(case)},
    )


@login_required
@require_POST
def case_ai_save(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    subject = request.POST.get("subject", "").strip()
    body = request.POST.get("body", "").strip()
    if not subject or not body:
        messages.error(request, "The AI draft is empty. Generate it again.")
        return redirect("case-compose", pk=case.pk)
    if len(body) > assist.MAX_OUTPUT_CHARS:
        messages.error(request, "The AI draft is too long.")
        return redirect("case-compose", pk=case.pk)
    template = _selected_ai_template(case, request)
    locale = template.locale if template else AppSettings.load().default_locale
    config = llm.resolve_config()
    try:
        message = assist.create_ai_draft(
            case,
            subject=subject,
            body=body,
            provider=config.provider,
            model=config.model,
            to_address=request.POST.get("to_address", ""),
            template=template,
            locale=locale,
            actor=request.user,
            request=request,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("case-compose", pk=case.pk)
    messages.success(request, "AI-generated draft saved. Review it before sending.")
    return redirect("message-detail", pk=case.pk, message_pk=message.pk)


@login_required
@require_POST
def case_ai_apply_scope(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    try:
        assist.apply_ai_scope(
            case,
            request.POST.get("scope", ""),
            actor=request.user,
            request=request,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Scope updated with AI assistance.")
    return redirect(case)


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
