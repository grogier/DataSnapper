from __future__ import annotations

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from core.utils import format_file_size

register = template.Library()

STATUS_CLASSES = {
    "draft": "badge-neutral",
    "queued": "badge-info",
    "sent": "badge-info",
    "acknowledged": "badge-info",
    "identity_check": "badge-warning",
    "in_progress": "badge-info",
    "partially_fulfilled": "badge-warning",
    "fulfilled": "badge-success",
    "refused": "badge-danger",
    "no_response": "badge-danger",
    "escalated": "badge-danger",
    "withdrawn": "badge-neutral",
    "closed": "badge-neutral",
    "open": "badge-info",
    "done": "badge-success",
    "cancelled": "badge-neutral",
    "high": "badge-danger",
    "normal": "badge-neutral",
    "low": "badge-neutral",
}


@register.filter
def badge_class(value: str) -> str:
    return STATUS_CLASSES.get(str(value).lower(), "badge-neutral")


@register.filter
def get_item(mapping, key):
    if hasattr(mapping, "get"):
        return mapping.get(key)
    return None


@register.filter
def file_size(value) -> str:
    return format_file_size(value)


@register.filter
def dash(value) -> str:
    return value if value not in (None, "", []) else "—"


@register.filter
def right_label(value: str) -> str:
    from cases.rights import right_definition

    definition = right_definition(value)
    return definition["label"] if definition else value


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.simple_tag
def priority_dot(priority: str):
    colours = {"high": "#b42318", "normal": "#175cd3", "low": "#667085"}
    colour = colours.get(priority, "#667085")
    return format_html(
        '<span class="dot" style="background:{}" title="{}"></span>', colour, priority
    )


@register.filter
def safe_lines(value: str) -> str:
    return mark_safe("<br>".join(escape(line) for line in str(value).splitlines()))
