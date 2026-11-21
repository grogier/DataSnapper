from __future__ import annotations

import time

from core.llm.http import request_json
from core.llm.schema import LLMConfig, LLMResponseError, LLMResult


def build_payload(config: LLMConfig, system: str, user: str, *, json_mode: bool) -> dict:
    payload: dict = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": config.temperature,
            "num_predict": config.max_tokens,
        },
    }
    if json_mode:
        payload["format"] = "json"
    return payload


def _url(config: LLMConfig, path: str) -> str:
    return config.base_url.rstrip("/") + path


def chat(config: LLMConfig, system: str, user: str, *, json_mode: bool = True) -> LLMResult:
    payload = build_payload(config, system, user, json_mode=json_mode)
    started = time.monotonic()
    data = request_json(
        "POST",
        _url(config, "/api/chat"),
        payload=payload,
        timeout=config.timeout,
    )
    duration_ms = int((time.monotonic() - started) * 1000)

    message = data.get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise LLMResponseError("Ollama returned an empty response.")

    return LLMResult(
        text=text,
        provider=config.provider,
        model=str(data.get("model") or config.model),
        duration_ms=duration_ms,
        prompt_tokens=int(data.get("prompt_eval_count") or 0),
        completion_tokens=int(data.get("eval_count") or 0),
        finish_reason=str(data.get("done_reason") or ""),
    )


def list_models(config: LLMConfig) -> list[str]:
    data = request_json(
        "GET",
        _url(config, "/api/tags"),
        timeout=min(config.timeout, 30),
    )
    items = data.get("models") or []
    names = {str(item.get("name")) for item in items if isinstance(item, dict) and item.get("name")}
    return sorted(names)
