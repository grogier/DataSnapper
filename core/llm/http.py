from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from core.llm.schema import LLMConnectionError, LLMResponseError

USER_AGENT = "DataSnapper/0.1"


def _error_detail(raw: bytes) -> str:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return raw.decode("utf-8", errors="replace").strip()[:300]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)[:300]
        if error:
            return str(error)[:300]
        if data.get("message"):
            return str(data["message"])[:300]
    return json.dumps(data)[:300]


def request_json(
    method: str,
    url: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)

    try:
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except ValueError as exc:
        raise LLMConnectionError(f"Invalid endpoint URL: {url}") from exc
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc.read())
        if exc.code == 401:
            message = "The API key was rejected (401). Check the key in your environment."
        elif exc.code == 403:
            message = "The provider refused access (403). Check the API key and account."
        elif exc.code == 429:
            message = "The provider is rate limiting requests (429). Try again shortly."
        elif exc.code >= 500:
            message = f"The provider had a server error ({exc.code}). Try again later."
        else:
            message = f"The provider returned HTTP {exc.code}."
        if detail:
            message = f"{message} {detail}"
        raise LLMConnectionError(message, status=exc.code) from exc
    except TimeoutError as exc:
        raise LLMConnectionError(f"Timed out after {timeout} seconds waiting for {url}.") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise LLMConnectionError(f"Could not reach {url}: {reason}") from exc

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LLMResponseError("The provider returned a response that was not valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("The provider returned an unexpected response.")
    return parsed
