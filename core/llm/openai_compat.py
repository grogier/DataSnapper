from __future__ import annotations

import time

from core.llm.http import request_json
from core.llm.providers import provider_spec
from core.llm.schema import (
    LLMConfig,
    LLMConnectionError,
    LLMResponseError,
    LLMResult,
)


def build_payload(config: LLMConfig, system: str, user: str, *, json_mode: bool) -> dict:
    spec = provider_spec(config.provider)
    payload: dict = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "max_tokens": config.max_tokens,
    }

    if spec.supports_thinking:
        if config.reasoning:
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = "high"
        else:
            payload["thinking"] = {"type": "disabled"}
            payload["temperature"] = config.temperature
    else:
        payload["temperature"] = config.temperature

    if json_mode and spec.supports_json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _headers(config: LLMConfig) -> dict[str, str]:
    if not config.api_key:
        return {}
    return {"Authorization": f"Bearer {config.api_key}"}


def _url(config: LLMConfig, path: str) -> str:
    return config.base_url.rstrip("/") + path


def chat(config: LLMConfig, system: str, user: str, *, json_mode: bool = True) -> LLMResult:
    payload = build_payload(config, system, user, json_mode=json_mode)
    started = time.monotonic()
    try:
        data = request_json(
            "POST",
            _url(config, "/chat/completions"),
            payload=payload,
            headers=_headers(config),
            timeout=config.timeout,
        )
    except LLMConnectionError as exc:
        # Not every OpenAI-compatible endpoint implements response_format.
        if exc.status == 400 and "response_format" in str(exc).lower():
            payload.pop("response_format", None)
            data = request_json(
                "POST",
                _url(config, "/chat/completions"),
                payload=payload,
                headers=_headers(config),
                timeout=config.timeout,
            )
        else:
            raise
    duration_ms = int((time.monotonic() - started) * 1000)

    choices = data.get("choices") or []
    if not choices:
        raise LLMResponseError("The provider returned no response choices.")
    choice = choices[0]
    finish_reason = str(choice.get("finish_reason") or "")
    message = choice.get("message") or {}
    text = str(message.get("content") or "").strip()
    usage = data.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}

    if finish_reason == "content_filter":
        raise LLMResponseError("The provider blocked the response with a content filter.")
    if finish_reason == "length":
        raise LLMResponseError(
            "The response was cut off before it was complete. Try again or raise the output limit."
        )
    if finish_reason in {"insufficient_system_resource", "aborted"}:
        raise LLMResponseError("The provider interrupted the response. Try again.")
    if not text:
        raise LLMResponseError("The provider returned an empty response.")

    return LLMResult(
        text=text,
        provider=config.provider,
        model=str(data.get("model") or config.model),
        duration_ms=duration_ms,
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        reasoning_tokens=int(details.get("reasoning_tokens") or 0),
        cached_tokens=int(usage.get("prompt_cache_hit_tokens") or 0),
        finish_reason=finish_reason,
    )


def list_models(config: LLMConfig) -> list[str]:
    data = request_json(
        "GET",
        _url(config, "/models"),
        headers=_headers(config),
        timeout=min(config.timeout, 30),
    )
    items = data.get("data") or []
    names = {str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")}
    return sorted(names)
