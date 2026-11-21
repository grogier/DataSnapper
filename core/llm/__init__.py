from __future__ import annotations

import os
import time

from core.llm import ollama, openai_compat
from core.llm.providers import (
    PROVIDER_CHOICES,
    PROVIDERS,
    api_key_for,
    endpoint_is_local,
    provider_spec,
)
from core.llm.schema import (
    LLMConfig,
    LLMConfigError,
    LLMConnectionError,
    LLMError,
    LLMResponseError,
    LLMResult,
)

__all__ = [
    "PROVIDERS",
    "PROVIDER_CHOICES",
    "LLMConfig",
    "LLMConfigError",
    "LLMConnectionError",
    "LLMError",
    "LLMResponseError",
    "LLMResult",
    "api_key_for",
    "endpoint_is_local",
    "env_overrides",
    "generate",
    "provider_spec",
    "require_config",
    "resolve_config",
    "settings_status",
    "test_connection",
]


def _env_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(raw: str) -> int:
    return int(raw.strip())


def _env_str(raw: str) -> str:
    return raw.strip()


_ENV_FIELDS: dict[str, tuple[str, object, object]] = {
    "llm_enabled": ("LLM_ENABLED", _env_bool, False),
    "llm_provider": ("LLM_PROVIDER", _env_str, "ollama"),
    "llm_base_url": ("LLM_BASE_URL", _env_str, ""),
    "llm_model": ("LLM_MODEL", _env_str, ""),
    "llm_timeout": ("LLM_TIMEOUT", _env_int, 120),
    "llm_max_output_tokens": ("LLM_MAX_OUTPUT_TOKENS", _env_int, 1500),
    "llm_reasoning": ("LLM_REASONING", _env_bool, False),
    "llm_share_personal_data": ("LLM_SHARE_PERSONAL_DATA", _env_bool, False),
}


def env_overrides() -> list[str]:
    names: list[str] = []
    for env_name, _, _ in _ENV_FIELDS.values():
        if os.environ.get(env_name, "").strip():
            names.append(env_name)
    return names


def _env_value(attr: str):
    env_name, parser, _ = _ENV_FIELDS[attr]
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return None
    try:
        return parser(raw)
    except (TypeError, ValueError):
        return None


def _db_value(settings_obj, attr: str, default):
    return getattr(settings_obj, attr, default)


def resolve_config(settings_obj=None) -> LLMConfig:
    if settings_obj is None:
        from core.models import AppSettings

        settings_obj = AppSettings.load()

    db_provider = str(_db_value(settings_obj, "llm_provider", "ollama") or "ollama")
    provider = _env_value("llm_provider") or db_provider
    if provider not in PROVIDERS:
        provider = "ollama"
    spec = provider_spec(provider)
    provider_changed = provider != db_provider

    env_base_url = _env_value("llm_base_url")
    if env_base_url:
        base_url = str(env_base_url)
    elif provider_changed:
        base_url = spec.default_base_url
    else:
        base_url = str(_db_value(settings_obj, "llm_base_url", "") or "") or spec.default_base_url

    env_model = _env_value("llm_model")
    if env_model:
        model = str(env_model)
    elif provider_changed:
        model = spec.default_model
    else:
        model = str(_db_value(settings_obj, "llm_model", "") or "") or spec.default_model

    enabled = _env_value("llm_enabled")
    if enabled is None:
        enabled = bool(_db_value(settings_obj, "llm_enabled", False))

    timeout = _env_value("llm_timeout")
    if timeout is None:
        timeout = int(_db_value(settings_obj, "llm_timeout", 120) or 120)

    max_tokens = _env_value("llm_max_output_tokens")
    if max_tokens is None:
        max_tokens = int(_db_value(settings_obj, "llm_max_output_tokens", 1500) or 1500)

    reasoning = _env_value("llm_reasoning")
    if reasoning is None:
        reasoning = bool(_db_value(settings_obj, "llm_reasoning", False))

    share_personal = _env_value("llm_share_personal_data")
    if share_personal is None:
        share_personal = bool(_db_value(settings_obj, "llm_share_personal_data", False))

    api_key, _ = api_key_for(provider)

    return LLMConfig(
        enabled=bool(enabled),
        provider=provider,
        base_url=base_url.rstrip("/"),
        model=model,
        api_key=api_key,
        timeout=max(5, min(int(timeout), 600)),
        max_tokens=max(100, min(int(max_tokens), 8000)),
        reasoning=bool(reasoning),
        share_personal_data=bool(share_personal),
    )


def require_config(settings_obj=None) -> LLMConfig:
    config = resolve_config(settings_obj)
    if not config.enabled:
        raise LLMConfigError("AI assistance is disabled. Enable it in Settings first.")
    spec = provider_spec(config.provider)
    if spec.api_key_envs and not config.api_key and not endpoint_is_local(config.base_url):
        names = " or ".join(spec.api_key_envs)
        raise LLMConfigError(
            f"No API key is configured. Set {names} in the environment and restart."
        )
    return config


def generate(
    system: str,
    user: str,
    *,
    config: LLMConfig | None = None,
    json_mode: bool = True,
) -> LLMResult:
    if config is None:
        config = require_config()
    if provider_spec(config.provider).kind == "ollama":
        return ollama.chat(config, system, user, json_mode=json_mode)
    return openai_compat.chat(config, system, user, json_mode=json_mode)


def test_connection(config: LLMConfig | None = None) -> dict:
    if config is None:
        config = resolve_config()
    spec = provider_spec(config.provider)
    if spec.api_key_envs and not config.api_key and not endpoint_is_local(config.base_url):
        names = " or ".join(spec.api_key_envs)
        raise LLMConfigError(
            f"No API key is configured. Set {names} in the environment and restart."
        )

    started = time.monotonic()
    note = ""
    if spec.kind == "ollama":
        models = ollama.list_models(config)
    else:
        try:
            models = openai_compat.list_models(config)
        except LLMConnectionError as exc:
            if exc.status not in {404, 405}:
                raise
            openai_compat.chat(
                config,
                "You are a connection test.",
                "Reply with the single word OK.",
                json_mode=False,
            )
            models = []
            note = "The model list is unavailable, but a test prompt succeeded."

    return {
        "provider": spec.label,
        "model": config.model,
        "models": models,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "note": note,
    }


def settings_status(settings_obj=None) -> dict:
    if settings_obj is None:
        from core.models import AppSettings

        settings_obj = AppSettings.load()
    config = resolve_config(settings_obj)
    spec = provider_spec(config.provider)
    key, env_name = api_key_for(config.provider)
    key_required = bool(spec.api_key_envs) and not endpoint_is_local(config.base_url)
    return {
        "provider": config.provider,
        "provider_label": spec.label,
        "base_url": config.base_url,
        "model": config.model,
        "enabled": config.enabled,
        "key_required": key_required,
        "key_configured": bool(key) or not key_required,
        "key_env_name": env_name,
        "is_cloud": not endpoint_is_local(config.base_url),
        "supports_thinking": spec.supports_thinking,
        "share_personal_data": config.share_personal_data,
        "overrides": env_overrides(),
    }
