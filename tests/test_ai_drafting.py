from __future__ import annotations

import pytest
from django.urls import reverse

from audit.models import AuditLog
from cases.models import CaseEvent
from core import llm
from core.llm.schema import LLMResponseError, LLMResult
from core.models import AppSettings
from correspondence import assist
from correspondence.models import Message, Template
from correspondence.services import create_draft_message


def _enable_ollama():
    settings_obj = AppSettings.load()
    settings_obj.llm_enabled = True
    settings_obj.llm_provider = "ollama"
    settings_obj.llm_base_url = "http://localhost:11434"
    settings_obj.llm_model = "llama3.1:8b"
    settings_obj.save()
    return settings_obj


def test_placeholder_mode_hides_personal_data(case, profile):
    bundle = assist.build_prompt(case, mode="draft", locale="en")
    assert "Test Person" not in bundle.user
    assert "Teststraat" not in bundle.user
    assert "{{ profile.full_name }}" in bundle.user
    assert "access" in bundle.user.lower()
    # Notes typed by the user are sent as written, so do not put secrets in them.
    assert "Account me@example.com" in bundle.user


def test_personal_mode_includes_details(case, profile):
    bundle = assist.build_prompt(case, mode="draft", locale="en", include_personal=True)
    assert "Test Person" in bundle.user
    assert "me@example.com" in bundle.user
    assert "{{ profile.full_name }}" in bundle.user


def test_env_can_enable_personal_data(case, profile, monkeypatch):
    monkeypatch.setenv("LLM_SHARE_PERSONAL_DATA", "1")
    config = llm.resolve_config()
    assert config.share_personal_data is True
    bundle = assist.build_prompt(
        case,
        mode="draft",
        locale="en",
        include_personal=config.share_personal_data,
    )
    assert "Test Person" in bundle.user


def test_parse_result_strips_code_fences(case):
    result = assist.parse_result(
        '```json\n{"subject": "Access request", "body": "Hello {{ profile.full_name }}",'
        ' "scope": ""}\n```',
        mode="draft",
        case=case,
    )
    assert result.subject == "Access request"
    assert result.body == "Hello {{ profile.full_name }}"


def test_parse_result_rejects_unknown_placeholder(case):
    with pytest.raises(LLMResponseError, match="unknown placeholders"):
        assist.parse_result(
            '{"subject": "x", "body": "Hi {{ profile.nope }}", "scope": ""}',
            mode="draft",
            case=case,
        )


def test_parse_scope_requires_scope(case):
    with pytest.raises(LLMResponseError, match="did not return a scope"):
        assist.parse_result('{"subject": "", "body": "", "scope": ""}', mode="scope", case=case)


def test_create_ai_draft_sets_provenance(case, user, profile):
    message = assist.create_ai_draft(
        case,
        subject="Access request for {{ profile.full_name }}",
        body="Hello {{ profile.full_name }}",
        provider="ollama",
        model="llama3.1:8b",
        actor=user,
    )
    assert message.ai_generated is True
    assert message.ai_provider == "ollama"
    assert message.ai_model == "llama3.1:8b"
    assert message.status == Message.Status.DRAFT
    assert message.subject == "Access request for Test Person"
    assert message.body == "Hello Test Person"
    assert AuditLog.objects.filter(action="message.ai_draft").exists()
    assert CaseEvent.objects.filter(
        case=case, summary__startswith="AI-generated draft prepared"
    ).exists()


def test_message_source_labels(case, user, profile, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)

    ai_message = assist.create_ai_draft(
        case,
        subject="AI letter",
        body="AI body",
        provider="ollama",
        model="llama3.1:8b",
        template=template,
        actor=user,
    )
    assert ai_message.source_label == "AI-generated"
    assert ai_message.source_detail == "ollama · llama3.1:8b"

    template_message = create_draft_message(case, template, actor=user)
    assert template_message.source_label == "From template"
    assert template_message.source_detail == f"{template.name} v{template.version}"

    free_message = Message.objects.create(case=case, subject="Free", body="Free body")
    assert free_message.source_label == "Free text"
    assert free_message.source_detail == ""


def test_message_detail_shows_ai_provenance(client_logged_in, case, user, profile):
    message = assist.create_ai_draft(
        case,
        subject="AI letter",
        body="AI body",
        provider="ollama",
        model="llama3.1:8b",
        actor=user,
    )
    response = client_logged_in.get(reverse("message-detail", args=[case.pk, message.pk]))
    assert response.status_code == 200
    assert b"AI-generated" in response.content
    assert b"ollama" in response.content


def test_message_detail_shows_template_provenance(client_logged_in, case, user, profile, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    message = create_draft_message(case, template, actor=user)
    response = client_logged_in.get(reverse("message-detail", args=[case.pk, message.pk]))
    assert response.status_code == 200
    assert b"From template" in response.content
    assert b"no AI used" in response.content


def test_apply_ai_scope_updates_case_and_audit(case, user):
    assist.apply_ai_scope(case, "All data linked to account 123 since 2020.", actor=user)
    case.refresh_from_db()
    assert case.scope == "All data linked to account 123 since 2020."
    assert AuditLog.objects.filter(action="case.scope_ai").exists()
    assert CaseEvent.objects.filter(case=case, summary="Scope updated with AI assistance").exists()


def test_generate_assist_uses_llm_and_logs(case, user, monkeypatch):
    _enable_ollama()
    captured: dict = {}

    def fake_generate(system, prompt, *, config=None, json_mode=True):
        captured["system"] = system
        captured["prompt"] = prompt
        captured["config"] = config
        return LLMResult(
            text='{"subject": "", "body": "", "scope": "All data linked to my account."}',
            provider="ollama",
            model="llama3.1:8b",
            duration_ms=42,
            prompt_tokens=10,
            completion_tokens=5,
        )

    monkeypatch.setattr(llm, "generate", fake_generate)
    result, meta, bundle = assist.generate_assist(
        case,
        mode="scope",
        locale="en",
        actor=user,
    )
    assert result.scope == "All data linked to my account."
    assert meta.duration_ms == 42
    assert captured["config"].provider == "ollama"
    assert bundle.prompt_sha256
    entry = AuditLog.objects.get(action="llm.generate")
    assert entry.metadata["provider"] == "ollama"
    assert entry.metadata["prompt_sha256"] == bundle.prompt_sha256
    assert "All data linked" not in str(entry.metadata)


def test_generate_assist_retries_invalid_json(case, user, profile, monkeypatch):
    _enable_ollama()
    calls: list[str] = []

    def fake_generate(system, prompt, *, config=None, json_mode=True):
        calls.append(prompt)
        text = "not json" if len(calls) == 1 else '{"scope": "All data linked to my account."}'
        return LLMResult(
            text=text,
            provider="ollama",
            model="llama3.1:8b",
            duration_ms=3,
        )

    monkeypatch.setattr(llm, "generate", fake_generate)
    result, _meta, _bundle = assist.generate_assist(case, mode="scope", locale="en", actor=user)
    assert result.scope == "All data linked to my account."
    assert len(calls) == 2
    entry = AuditLog.objects.get(action="llm.generate")
    assert entry.metadata["retried"] is True
    assert entry.metadata["retry_prompt_sha256"]


def test_generate_assist_reports_disabled(case, user):
    with pytest.raises(llm.LLMConfigError, match="disabled"):
        assist.generate_assist(case, mode="scope", locale="en", actor=user)


@pytest.fixture
def enabled_ai(db):
    return _enable_ollama()


def test_ai_generate_view_returns_partial(client_logged_in, case, enabled_ai, monkeypatch):
    monkeypatch.setattr(
        llm,
        "generate",
        lambda *args, **kwargs: LLMResult(
            text='{"subject": "", "body": "", "scope": "All records for my account."}',
            provider="ollama",
            model="llama3.1:8b",
            duration_ms=12,
        ),
    )
    response = client_logged_in.post(
        reverse("case-ai-generate", args=[case.pk]),
        {"mode": "scope", "tone": "neutral", "length": "concise"},
    )
    assert response.status_code == 200
    assert b"All records for my account." in response.content
    assert b"Use this scope" in response.content
    assert b"AI responded" in response.content


def test_ai_generate_view_reports_disabled(client_logged_in, case):
    response = client_logged_in.post(
        reverse("case-ai-generate", args=[case.pk]),
        {"mode": "scope"},
    )
    assert response.status_code == 200
    assert b"disabled" in response.content


def test_ai_prompt_view_shows_payload(client_logged_in, case, enabled_ai):
    response = client_logged_in.post(
        reverse("case-ai-prompt", args=[case.pk]),
        {"mode": "draft", "tone": "neutral", "length": "concise"},
    )
    assert response.status_code == 200
    assert b"System prompt" in response.content
    assert b"{{ profile.full_name }}" in response.content


def test_ai_save_view_creates_draft(client_logged_in, case, enabled_ai):
    response = client_logged_in.post(
        reverse("case-ai-save", args=[case.pk]),
        {
            "subject": "Access request",
            "body": "Dear {{ organization.name }}, please provide my data.",
            "to_address": "privacy@example.com",
        },
    )
    assert response.status_code == 302
    message = Message.objects.get(case=case)
    assert message.ai_generated is True
    assert message.subject == "Access request"


def test_ai_apply_scope_view(client_logged_in, case, enabled_ai):
    response = client_logged_in.post(
        reverse("case-ai-apply-scope", args=[case.pk]),
        {"scope": "Everything linked to my account since 2019."},
    )
    assert response.status_code == 302
    case.refresh_from_db()
    assert case.scope == "Everything linked to my account since 2019."


def test_rewrite_rendered_message_requires_sharing(client_logged_in, case, enabled_ai, user):
    message = Message.objects.create(
        case=case,
        subject="Old draft",
        body="Rendered personal text",
        status=Message.Status.DRAFT,
    )
    response = client_logged_in.post(
        reverse("case-ai-generate", args=[case.pk]),
        {"mode": "rewrite", "message_pk": message.pk},
    )
    assert response.status_code == 200
    assert b"Share personal data" in response.content


def test_ai_template_body_can_be_rewritten(
    client_logged_in, case, enabled_ai, templates, monkeypatch
):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    monkeypatch.setattr(
        llm,
        "generate",
        lambda *args, **kwargs: LLMResult(
            text='{"subject": "Better", "body": "Better {{ profile.full_name }}", "scope": ""}',
            provider="ollama",
            model="llama3.1:8b",
            duration_ms=5,
        ),
    )
    response = client_logged_in.post(
        reverse("case-ai-generate", args=[case.pk]),
        {"mode": "rewrite", "template": template.pk},
    )
    assert response.status_code == 200
    assert b"Better" in response.content
    assert b"AI-generated draft" in response.content
    assert b"AI wrote this letter" in response.content
    assert b"Template: Access request v1" in response.content


def test_prompt_uses_template_as_base(case, profile, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    bundle = assist.build_prompt(
        case,
        mode="draft",
        locale="en",
        scope="Account other@example.com since 2019.",
        template_subject=template.subject,
        template_body=template.body,
    )
    assert "BASE TEMPLATE" in bundle.user
    assert "the purposes of the processing;" in bundle.user
    assert "Account other@example.com since 2019." in bundle.user
    assert "Account me@example.com and purchase history since 2020." not in bundle.user


def test_generate_view_combines_template_and_scope(
    client_logged_in, case, enabled_ai, templates, monkeypatch
):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    captured: dict = {}

    def fake_generate(system, prompt, *, config=None, json_mode=True):
        captured["prompt"] = prompt
        return LLMResult(
            text='{"subject": "Access", "body": "Hello {{ profile.full_name }}", "scope": ""}',
            provider="ollama",
            model="llama3.1:8b",
            duration_ms=5,
        )

    monkeypatch.setattr(llm, "generate", fake_generate)
    response = client_logged_in.post(
        reverse("case-ai-generate", args=[case.pk]),
        {
            "mode": "draft",
            "template": template.pk,
            "scope": "My other account, other@example.com.",
            "extra_note": "Mention the old newsletter.",
        },
    )
    assert response.status_code == 200
    assert "BASE TEMPLATE" in captured["prompt"]
    assert "the purposes of the processing;" in captured["prompt"]
    assert "My other account, other@example.com." in captured["prompt"]
    assert "Mention the old newsletter." in captured["prompt"]


def test_template_preview_editor_saves_edits(client_logged_in, case, profile, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    response = client_logged_in.post(
        reverse("case-compose", args=[case.pk]),
        {"template": template.pk, "action": "preview"},
    )
    assert response.status_code == 200
    assert b"preview-body" in response.content

    response = client_logged_in.post(
        reverse("case-compose", args=[case.pk]),
        {
            "action": "save",
            "template": template.pk,
            "to_address": "privacy@example.com",
            "subject": "Edited subject",
            "body": "Edited body",
        },
    )
    assert response.status_code == 302
    message = Message.objects.get(case=case)
    assert message.subject == "Edited subject"
    assert message.body == "Edited body"
    assert message.template == template


def test_ai_save_links_the_template_version(client_logged_in, case, enabled_ai, templates):
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    response = client_logged_in.post(
        reverse("case-ai-save", args=[case.pk]),
        {
            "subject": "Access request",
            "body": "Dear {{ organization.name }}, please provide my data.",
            "template": template.pk,
        },
    )
    assert response.status_code == 302
    message = Message.objects.get(case=case)
    assert message.template == template
    assert message.template_version == template.version
    assert message.ai_generated is True


def test_compose_page_renders_ai_first_form(client_logged_in, case, profile, templates, enabled_ai):
    response = client_logged_in.get(reverse("case-compose", args=[case.pk]))
    assert response.status_code == 200
    assert b"Write the letter" in response.content
    assert b"Generate letter" in response.content
    assert b"Fill from template" in response.content
    assert b"Points to emphasise" in response.content


def test_compose_page_without_templates_still_allows_ai(
    client_logged_in, case, profile, enabled_ai
):
    response = client_logged_in.get(reverse("case-compose", args=[case.pk]))
    assert response.status_code == 200
    assert b"No template (draft from scratch)" in response.content
    assert b"Generate letter" in response.content
    assert b"Fill from template" not in response.content


def test_settings_shows_configured_key(client_logged_in, db, monkeypatch):
    settings_obj = AppSettings.load()
    settings_obj.llm_provider = "deepseek"
    settings_obj.llm_base_url = "https://api.deepseek.com"
    settings_obj.llm_model = "deepseek-flash"
    settings_obj.save()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    response = client_logged_in.get(reverse("settings"))
    assert response.status_code == 200
    assert b"Configured via" in response.content
    assert b"sk-test" not in response.content


def test_llm_settings_form_saves(client_logged_in, db):
    response = client_logged_in.post(
        reverse("settings"),
        {
            "form_type": "llm",
            "llm_enabled": "on",
            "llm_provider": "deepseek",
            "llm_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-v4-pro",
            "llm_timeout": "120",
            "llm_max_output_tokens": "2000",
            "llm_reasoning": "on",
        },
    )
    assert response.status_code == 302
    settings_obj = AppSettings.load()
    assert settings_obj.llm_enabled is True
    assert settings_obj.llm_provider == "deepseek"
    assert settings_obj.llm_model == "deepseek-v4-pro"
    assert settings_obj.llm_reasoning is True


def test_llm_connection_test_view(client_logged_in, db, monkeypatch):
    monkeypatch.setattr(
        llm,
        "test_connection",
        lambda config: {
            "provider": "Ollama (local)",
            "model": "llama3.1:8b",
            "models": ["llama3.1:8b"],
            "duration_ms": 4,
            "note": "",
        },
    )
    response = client_logged_in.post(reverse("settings-llm-test"))
    assert response.status_code == 200
    assert b"answered in 4 ms" in response.content
