from __future__ import annotations

import os
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    kind: str
    default_base_url: str
    default_model: str
    api_key_envs: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    is_cloud: bool = False
    supports_json_mode: bool = True
    supports_thinking: bool = False
    note: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "ollama": ProviderSpec(
        key="ollama",
        label="Ollama (local)",
        kind="ollama",
        default_base_url="http://localhost:11434",
        default_model="llama3.1:8b",
        models=("llama3.1:8b", "qwen2.5:7b", "mistral-nemo"),
        note="Runs on your machine. No prompt data leaves the host.",
    ),
    "openai": ProviderSpec(
        key="openai",
        label="OpenAI-compatible",
        kind="openai",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        api_key_envs=("OPENAI_API_KEY", "LLM_API_KEY"),
        models=("gpt-4o-mini", "gpt-4.1-mini"),
        is_cloud=True,
        note="Use any OpenAI-compatible endpoint, including OpenRouter, Groq or LM Studio.",
    ),
    "deepseek": ProviderSpec(
        key="deepseek",
        label="DeepSeek (cloud)",
        kind="openai",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-flash",
        api_key_envs=("DEEPSEEK_API_KEY", "LLM_API_KEY"),
        models=("deepseek-flash", "deepseek-v4-pro"),
        is_cloud=True,
        supports_thinking=True,
        note="Cloud service outside the EU. Prompts leave this machine.",
    ),
}

PROVIDER_CHOICES = [(spec.key, spec.label) for spec in PROVIDERS.values()]


def provider_spec(key: str) -> ProviderSpec:
    return PROVIDERS.get(key, PROVIDERS["ollama"])


def api_key_for(provider: str) -> tuple[str, str]:
    """Return (key, environment variable name) for the provider."""
    spec = provider_spec(provider)
    for name in spec.api_key_envs:
        value = os.environ.get(name, "").strip()
        if value:
            return value, name
    default_name = spec.api_key_envs[0] if spec.api_key_envs else ""
    return "", default_name


def endpoint_is_local(url: str) -> bool:
    """Best-effort check whether an endpoint stays on the local network."""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return False
    if host in {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "host.docker.internal",
        "gateway.docker.internal",
    }:
        return True
    if host.endswith((".local", ".internal", ".lan", ".home")):
        return True
    if "." not in host:
        # Single-label hostnames such as a Compose service named "ollama".
        return True
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback
