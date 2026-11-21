from __future__ import annotations

import calendar
import hashlib
import re
from datetime import date
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template, TemplateSyntaxError
from django.utils.text import get_valid_filename

VARIABLE_RE = re.compile(r"{{\s*([A-Za-z_][\w.]*)\s*}}")

MONTHS = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "nl": [
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ],
}


def add_months(value: date, months: int) -> date:
    """Add calendar months, clamping the day to the end of the target month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def format_date(value: date | None, locale: str = "en") -> str:
    if value is None:
        return ""
    names = MONTHS.get(locale, MONTHS["en"])
    return f"{value.day} {names[value.month - 1]} {value.year}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_filename(name: str) -> str:
    cleaned = get_valid_filename(Path(name).name)
    return cleaned[:180] or "file"


def _key_file() -> Path:
    return Path(settings.DATA_DIR) / "field.key"


def get_fernet() -> Fernet:
    configured = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if configured:
        key = configured.encode("utf-8")
        try:
            return Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ImproperlyConfigured(
                "FIELD_ENCRYPTION_KEY is not a valid Fernet key (32 url-safe base64 bytes)."
            ) from exc

    path = _key_file()
    if path.exists():
        key = path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        path.write_bytes(key)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return Fernet(key)


def encrypt_bytes(data: bytes) -> bytes:
    return get_fernet().encrypt(data)


def decrypt_bytes(data: bytes) -> bytes:
    try:
        return get_fernet().decrypt(data)
    except InvalidToken as exc:
        raise ValueError("Could not decrypt this file with the configured key.") from exc


def render_text(text: str, context: dict, *, autoescape: bool = True) -> str:
    try:
        return Template(text).render(Context(context, autoescape=autoescape))
    except TemplateSyntaxError as exc:
        raise ValueError(f"Template syntax error: {exc}") from exc


def template_variables(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        for match in VARIABLE_RE.finditer(text or ""):
            name = match.group(1)
            if name not in found:
                found.append(name)
    return found


def missing_variables(texts: list[str], context: dict) -> list[str]:
    missing: list[str] = []
    for name in template_variables(*texts):
        root = name.split(".")[0]
        if root not in context:
            missing.append(name)
            continue
        value = context[root]
        for part in name.split(".")[1:]:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                missing.append(name)
                break
    return missing


def format_file_size(size: int | None) -> str:
    if not size:
        return "0 B"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
