from __future__ import annotations

from dataclasses import dataclass


class LLMError(Exception):
    """Base class for errors that can be shown to the user."""


class LLMConfigError(LLMError):
    """The LLM is disabled or not configured."""


class LLMConnectionError(LLMError):
    """The endpoint could not be reached or returned an HTTP error."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class LLMResponseError(LLMError):
    """The endpoint responded, but the body was not usable."""


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool
    provider: str
    base_url: str
    model: str
    api_key: str = ""
    timeout: int = 120
    max_tokens: int = 1500
    temperature: float = 0.3
    reasoning: bool = False
    share_personal_data: bool = False


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    finish_reason: str = ""
