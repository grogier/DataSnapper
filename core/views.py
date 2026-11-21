from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.db import connection
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.models import AuditLog
from audit.services import log
from cases.models import Case, CaseEvent, Task
from companies.models import Organization
from core import llm
from core.forms import AppSettingsForm, DataSubjectForm, LLMSettingsForm
from core.llm.providers import PROVIDERS
from core.models import AppSettings, DataSubject
from core.utils import MONTHS
from correspondence.models import Attachment

OPEN_STATUSES = [
    Case.Status.DRAFT,
    Case.Status.QUEUED,
    Case.Status.SENT,
    Case.Status.ACKNOWLEDGED,
    Case.Status.IDENTITY_CHECK,
    Case.Status.IN_PROGRESS,
    Case.Status.PARTIALLY_FULFILLED,
    Case.Status.REFUSED,
    Case.Status.NO_RESPONSE,
    Case.Status.ESCALATED,
]


def _overdue_q(today: date):
    return Q(extended_due_at__lt=today) | Q(extended_due_at__isnull=True, due_at__lt=today)


def _due_soon_q(today: date):
    end = today + timedelta(days=10)
    return Q(extended_due_at__gte=today, extended_due_at__lte=end) | Q(
        extended_due_at__isnull=True, due_at__gte=today, due_at__lte=end
    )


@login_not_required
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse({"status": "error", "detail": str(exc)}, status=500)
    return JsonResponse({"status": "ok", "version": settings.APP_VERSION})


@login_required
def dashboard(request):
    today = timezone.localdate()
    open_cases = Case.objects.filter(status__in=OPEN_STATUSES)
    overdue_cases = (
        open_cases.filter(_overdue_q(today))
        .select_related("organization")
        .order_by("extended_due_at", "due_at")[:8]
    )
    due_soon_cases = (
        open_cases.filter(_due_soon_q(today))
        .exclude(_overdue_q(today))
        .select_related("organization")
        .order_by("extended_due_at", "due_at")[:8]
    )
    recent_events = CaseEvent.objects.select_related("case__organization", "actor")[:12]
    recent_cases = Case.objects.select_related("organization")[:6]
    upcoming_tasks = (
        Task.objects.filter(
            status=Task.Status.OPEN,
            due_at__isnull=False,
            due_at__lte=today + timedelta(days=14),
        )
        .select_related("case__organization")
        .order_by("due_at")[:8]
    )
    profile = DataSubject.get_primary()

    return render(
        request,
        "core/dashboard.html",
        {
            "today": today,
            "profile": profile,
            "stats": {
                "open_cases": open_cases.count(),
                "overdue": open_cases.filter(_overdue_q(today)).count(),
                "due_soon": open_cases.filter(_due_soon_q(today))
                .exclude(_overdue_q(today))
                .count(),
                "drafts": Case.objects.filter(status=Case.Status.DRAFT).count(),
                "organizations": Organization.objects.count(),
                "open_tasks": Task.objects.filter(status=Task.Status.OPEN).count(),
                "evidence": Attachment.objects.count(),
            },
            "overdue_cases": overdue_cases,
            "due_soon_cases": due_soon_cases,
            "recent_events": recent_events,
            "recent_cases": recent_cases,
            "upcoming_tasks": upcoming_tasks,
            "audit_ok": AuditLog.objects.exists(),
        },
    )


@login_required
def settings_view(request):
    profile = DataSubject.get_primary()
    app_settings = AppSettings.load()
    profile_form = DataSubjectForm(instance=profile)
    settings_form = AppSettingsForm(instance=app_settings)
    llm_form = LLMSettingsForm(instance=app_settings)

    if request.method == "POST":
        form_type = request.POST.get("form_type", "")
        if form_type == "profile":
            profile_form = DataSubjectForm(request.POST, instance=profile)
            if profile_form.is_valid():
                saved = profile_form.save(commit=False)
                saved.is_primary = True
                saved.save()
                DataSubject.objects.exclude(pk=saved.pk).update(is_primary=False)
                log(
                    actor=request.user,
                    action="settings.profile",
                    entity_type="data_subject",
                    entity_id=str(saved.pk),
                    summary="Updated personal profile",
                    request=request,
                )
                messages.success(request, "Profile saved.")
                return redirect("settings")
        elif form_type == "app":
            settings_form = AppSettingsForm(request.POST, instance=app_settings)
            if settings_form.is_valid():
                settings_form.save()
                log(
                    actor=request.user,
                    action="settings.app",
                    entity_type="app_settings",
                    entity_id=str(app_settings.pk),
                    summary="Updated application settings",
                    request=request,
                )
                messages.success(request, "Settings saved.")
                return redirect("settings")
        elif form_type == "llm":
            llm_form = LLMSettingsForm(request.POST, instance=app_settings)
            if llm_form.is_valid():
                llm_form.save()
                log(
                    actor=request.user,
                    action="settings.llm",
                    entity_type="app_settings",
                    entity_id=str(app_settings.pk),
                    summary="Updated AI assistance settings",
                    metadata={
                        "provider": app_settings.llm_provider,
                        "enabled": app_settings.llm_enabled,
                    },
                    request=request,
                )
                messages.success(request, "AI settings saved.")
                return redirect("settings")
        else:
            messages.error(request, "Unknown form submitted.")

    return render(
        request,
        "core/settings.html",
        {
            "profile": profile,
            "profile_form": profile_form,
            "settings_form": settings_form,
            "llm_form": llm_form,
            "llm_status": llm.settings_status(app_settings),
            "llm_presets": {
                key: {
                    "base_url": spec.default_base_url,
                    "model": spec.default_model,
                    "thinking": spec.supports_thinking,
                }
                for key, spec in PROVIDERS.items()
            },
            "data_dir": settings.DATA_DIR,
            "db_path": settings.DATABASES["default"]["NAME"],
            "media_root": settings.MEDIA_ROOT,
            "backup_dir": settings.BACKUP_DIR,
        },
    )


@login_required
@require_POST
def settings_llm_test(request):
    try:
        result = llm.test_connection(llm.resolve_config())
    except llm.LLMError as exc:
        log(
            actor=request.user,
            action="settings.llm_test",
            entity_type="app_settings",
            entity_id="1",
            summary="AI connection test failed",
            metadata={"error": exc.__class__.__name__},
            request=request,
        )
        return render(
            request,
            "core/_llm_status.html",
            {"ok": False, "error": str(exc)},
        )
    log(
        actor=request.user,
        action="settings.llm_test",
        entity_type="app_settings",
        entity_id="1",
        summary="AI connection test succeeded",
        metadata={"provider": result["provider"], "model": result["model"]},
        request=request,
    )
    return render(request, "core/_llm_status.html", {"ok": True, "result": result})


@login_required
def search_view(request):
    query = request.GET.get("q", "").strip()
    organizations = cases = messages_found = attachments = []
    if len(query) >= 2:
        organizations = Organization.objects.filter(
            Q(name__icontains=query)
            | Q(legal_name__icontains=query)
            | Q(trading_name__icontains=query)
            | Q(privacy_email__icontains=query)
        )[:15]
        cases = Case.objects.select_related("organization").filter(
            Q(reference__icontains=query)
            | Q(title__icontains=query)
            | Q(scope__icontains=query)
            | Q(notes__icontains=query)
            | Q(organization__name__icontains=query)
        )[:20]
        from correspondence.models import Message

        messages_found = Message.objects.select_related("case__organization").filter(
            Q(subject__icontains=query)
            | Q(body__icontains=query)
            | Q(case__reference__icontains=query)
        )[:20]
        attachments = Attachment.objects.select_related("case", "organization").filter(
            Q(original_name__icontains=query) | Q(notes__icontains=query)
        )[:20]
    return render(
        request,
        "core/search.html",
        {
            "query": query,
            "organizations": organizations,
            "cases": cases,
            "messages_found": messages_found,
            "attachments": attachments,
        },
    )


def _parse_month(value: str | None) -> date:
    if value:
        try:
            return datetime.strptime(value, "%Y-%m").date().replace(day=1)
        except ValueError:
            pass
    return timezone.localdate().replace(day=1)


@login_required
def calendar_view(request):
    first = _parse_month(request.GET.get("month"))
    year, month = first.year, first.month
    cal = calendar.Calendar(firstweekday=0)
    weeks_raw = cal.monthdatescalendar(year, month)
    range_start = weeks_raw[0][0]
    range_end = weeks_raw[-1][-1]

    cases = (
        Case.objects.select_related("organization")
        .filter(status__in=OPEN_STATUSES)
        .filter(
            Q(due_at__range=(range_start, range_end))
            | Q(extended_due_at__range=(range_start, range_end))
        )
    )
    tasks = Task.objects.select_related("case__organization").filter(
        status=Task.Status.OPEN, due_at__range=(range_start, range_end)
    )

    items: dict[date, list[dict]] = {}
    for case in cases:
        due = case.effective_due
        if due and range_start <= due <= range_end:
            items.setdefault(due, []).append(
                {
                    "type": "case",
                    "label": f"{case.reference} · {case.organization.name}",
                    "url": case.get_absolute_url(),
                    "tone": (
                        "danger"
                        if case.is_overdue
                        else (
                            "warning"
                            if case.days_left is not None and case.days_left <= 10
                            else "info"
                        )
                    ),
                }
            )
    for task in tasks:
        items.setdefault(task.due_at, []).append(
            {
                "type": "task",
                "label": f"Task · {task.title}",
                "url": task.case.get_absolute_url(),
                "tone": "warning" if task.is_overdue else "neutral",
            }
        )

    today = timezone.localdate()
    weeks = []
    for week in weeks_raw:
        days = []
        for day in week:
            days.append(
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "items": items.get(day, []),
                }
            )
        weeks.append(days)

    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    return render(
        request,
        "core/calendar.html",
        {
            "first": first,
            "month_label": f"{MONTHS['en'][month - 1]} {year}",
            "weeks": weeks,
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "prev_month": prev_month.strftime("%Y-%m"),
            "next_month": next_month.strftime("%Y-%m"),
            "today": today,
        },
    )


def _ics_escape(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ics_fold(line: str) -> list[str]:
    if len(line) <= 75:
        return [line]
    parts = [line[:75]]
    remainder = line[75:]
    while remainder:
        parts.append(" " + remainder[:74])
        remainder = remainder[74:]
    return parts


@login_required
def calendar_ics(request):
    now = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//DataSnapper//Privacy rights calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:DataSnapper deadlines",
    ]
    cases = Case.objects.select_related("organization").filter(status__in=OPEN_STATUSES)
    for case in cases:
        due = case.effective_due
        if not due:
            continue
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:case-{case.pk}@datasnapper",
                f"DTSTAMP:{now}",
                f"DTSTART;VALUE=DATE:{due:%Y%m%d}",
                f"SUMMARY:{_ics_escape(f'{case.reference} {case.right_label} - {case.organization.name}')}",
                f"DESCRIPTION:{_ics_escape(case.scope or case.get_status_display())}",
                f"URL:{request.build_absolute_uri(case.get_absolute_url())}",
                "END:VEVENT",
            ]
        )
    tasks = Task.objects.select_related("case").filter(
        status=Task.Status.OPEN, due_at__isnull=False
    )
    for task in tasks:
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:task-{task.pk}@datasnapper",
                f"DTSTAMP:{now}",
                f"DTSTART;VALUE=DATE:{task.due_at:%Y%m%d}",
                f"SUMMARY:{_ics_escape(f'Task: {task.title}')}",
                f"DESCRIPTION:{_ics_escape(task.case.reference)}",
                f"URL:{request.build_absolute_uri(task.case.get_absolute_url())}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    folded: list[str] = []
    for line in lines:
        folded.extend(_ics_fold(line))
    response = HttpResponse(
        "\r\n".join(folded) + "\r\n", content_type="text/calendar; charset=utf-8"
    )
    response["Content-Disposition"] = 'attachment; filename="datasnapper.ics"'
    return response
