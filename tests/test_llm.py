from __future__ import annotations

from dataclasses import replace

import pytest

from core import llm
from core.llm import ollama, openai_compat
from core.llm.providers import endpoint_is_local, provider_spec
from core.llm.schema import LLMConfig, LLMConfigError, LLMResponseError
from core.models import AppSettings


def test_defaults_are_local_ollama(db):
    config = llm.resolve_config()
    assert config.provider == "ollama"
    assert config.base_url == "http://localhost:11434"
    assert config.model == "llama3.1:8b"
    assert config.enabled is False


def test_env_overrides_provider_and_key(db, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    config = llm.resolve_config()
    assert config.provider == "deepseek"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-flash"
    assert config.api_key == "sk-test"


def test_db_settings_are_used(db):
    settings_obj = AppSettings.load()
    settings_obj.llm_enabled = True
    settings_obj.llm_provider = "deepseek"
    settings_obj.llm_base_url = "https://api.deepseek.com"
    settings_obj.llm_model = "deepseek-v4-pro"
    settings_obj.llm_reasoning = True
    settings_obj.save()

    config = llm.resolve_config()
    assert config.enabled is True
    assert config.provider == "deepseek"
    assert config.model == "deepseek-v4-pro"
    assert config.reasoning is True


def test_deepseek_defaults_to_no_thinking():
    config = LLMConfig(
        enabled=True,
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="sk-test",
    )
    payload = openai_compat.build_payload(config, "system", "user", json_mode=True)
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["temperature"] == 0.3
    assert "reasoning_effort" not in payload


def test_deepseek_reasoning_mode_omits_temperature():
    config = LLMConfig(
        enabled=True,
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="sk-test",
        reasoning=True,
    )
    payload = openai_compat.build_payload(config, "system", "user", json_mode=True)
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert "temperature" not in payload


def test_openai_payload_has_no_thinking_flag():
    spec = provider_spec("openai")
    assert spec.supports_thinking is False
    config = LLMConfig(
        enabled=True,
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="sk-test",
    )
    payload = openai_compat.build_payload(config, "system", "user", json_mode=True)
    assert "thinking" not in payload
    assert payload["temperature"] == 0.3


def test_openai_response_parsing_ignores_reasoning_content(monkeypatch):
    config = LLMConfig(
        enabled=True,
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="sk-test",
    )

    def fake_request(*args, **kwargs):
        return {
            "model": "deepseek-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": '{"subject": "x", "body": "y", "scope": ""}',
                        "reasoning_content": "private chain of thought",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "prompt_cache_hit_tokens": 4,
                "completion_tokens_details": {"reasoning_tokens": 7},
            },
        }

    monkeypatch.setattr(openai_compat, "request_json", fake_request)
    result = openai_compat.chat(config, "system", "user")
    assert result.text == '{"subject": "x", "body": "y", "scope": ""}'
    assert "private chain of thought" not in result.text
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 20
    assert result.cached_tokens == 4
    assert result.reasoning_tokens == 7


def test_truncated_response_is_rejected(monkeypatch):
    config = LLMConfig(
        enabled=True,
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="sk-test",
    )
    monkeypatch.setattr(
        openai_compat,
        "request_json",
        lambda *args, **kwargs: {
            "choices": [{"finish_reason": "length", "message": {"content": '{"body": "cut'}}]
        },
    )
    with pytest.raises(LLMResponseError, match="cut off"):
        openai_compat.chat(config, "system", "user")


def test_ollama_payload_and_parsing(monkeypatch):
    config = LLMConfig(
        enabled=True,
        provider="ollama",
        base_url="http://localhost:11434",
        model="llama3.1:8b",
    )
    payload = ollama.build_payload(config, "system", "user", json_mode=True)
    assert payload["format"] == "json"
    assert payload["options"]["num_predict"] == 1500
    assert payload["stream"] is False

    monkeypatch.setattr(
        ollama,
        "request_json",
        lambda *args, **kwargs: {
            "model": "llama3.1:8b",
            "message": {"content": '{"scope": "all data"}'},
            "prompt_eval_count": 12,
            "eval_count": 8,
            "done_reason": "stop",
        },
    )
    result = ollama.chat(config, "system", "user")
    assert result.text == '{"scope": "all data"}'
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 8


def test_endpoint_is_local_detection():
    assert endpoint_is_local("http://localhost:11434")
    assert endpoint_is_local("http://127.0.0.1:11434")
    assert endpoint_is_local("http://ollama:11434")
    assert endpoint_is_local("http://host.docker.internal:11434")
    assert endpoint_is_local("http://192.168.1.20:11434")
    assert not endpoint_is_local("https://api.deepseek.com")
    assert not endpoint_is_local("https://api.openai.com/v1")


def test_missing_key_is_reported(db):
    settings_obj = AppSettings.load()
    settings_obj.llm_enabled = True
    settings_obj.llm_provider = "deepseek"
    settings_obj.llm_base_url = "https://api.deepseek.com"
    settings_obj.save()
    with pytest.raises(LLMConfigError, match="DEEPSEEK_API_KEY"):
        llm.require_config()


def test_local_openai_endpoint_needs_no_key(db):
    settings_obj = AppSettings.load()
    settings_obj.llm_enabled = True
    settings_obj.llm_provider = "openai"
    settings_obj.llm_base_url = "http://localhost:1234/v1"
    settings_obj.llm_model = "local-model"
    settings_obj.save()
    config = llm.require_config()
    assert config.api_key == ""


def test_disabled_assistant_is_reported(db):
    with pytest.raises(LLMConfigError, match="disabled"):
        llm.require_config()


def test_test_connection_lists_models(db, monkeypatch):
    settings_obj = AppSettings.load()
    settings_obj.llm_provider = "deepseek"
    settings_obj.llm_base_url = "https://api.deepseek.com"
    settings_obj.llm_model = "deepseek-flash"
    settings_obj.save()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr(
        openai_compat,
        "request_json",
        lambda *args, **kwargs: {"data": [{"id": "deepseek-flash"}, {"id": "deepseek-v4-pro"}]},
    )
    result = llm.test_connection()
    assert result["provider"] == "DeepSeek (cloud)"
    assert result["models"] == ["deepseek-flash", "deepseek-v4-pro"]


def test_reasoning_override_uses_replace():
    config = LLMConfig(
        enabled=True,
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="sk-test",
    )
    updated = replace(config, reasoning=True)
    assert updated.reasoning is True
    assert config.reasoning is False
