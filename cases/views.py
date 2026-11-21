from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.services import log
from cases.forms import CaseForm, ExtendDeadlineForm, TaskForm, TransitionForm
from cases.models import Case, CaseEvent, Task
from cases.rights import RIGHT_CHOICES, checklist_for, initial_checklist
from cases.services import (
    add_event,
    create_case,
    extend_deadline,
    transition_case,
)
from companies.models import Organization
from core.models import DataSubject
from correspondence.forms import AttachmentForm

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


@login_required
def case_list(request):
    cases = (
        Case.objects.select_related("organization")
        .annotate(
            message_count=Count("messages", distinct=True),
            open_task_count=Count("tasks", filter=Q(tasks__status=Task.Status.OPEN), distinct=True),
        )
        .order_by("-opened_at", "-id")
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    right = request.GET.get("right", "")
    organization = request.GET.get("organization", "")
    overdue = request.GET.get("overdue", "")

    if query:
        cases = cases.filter(
            Q(reference__icontains=query)
            | Q(title__icontains=query)
            | Q(scope__icontains=query)
            | Q(organization__name__icontains=query)
        )
    if status:
        cases = cases.filter(status=status)
    if right:
        cases = cases.filter(right=right)
    if organization:
        cases = cases.filter(organization_id=organization)
    if overdue == "1":
        today = timezone.localdate()
        cases = cases.filter(
            Q(due_at__lt=today, extended_due_at__isnull=True) | Q(extended_due_at__lt=today)
        ).exclude(status__in=[Case.Status.FULFILLED, Case.Status.WITHDRAWN, Case.Status.CLOSED])

    paginator = Paginator(cases, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "cases/list.html",
        {
            "page": page,
            "cases": page.object_list,
            "query": query,
            "status": status,
            "right": right,
            "organization": organization,
            "overdue": overdue,
            "statuses": Case.Status.choices,
            "rights": RIGHT_CHOICES,
            "organizations": Organization.objects.order_by("name"),
            "total": paginator.count,
            "open_count": Case.objects.filter(status__in=OPEN_STATUSES).count(),
        },
    )


@login_required
def case_create(request):
    initial = {}
    if request.GET.get("organization"):
        initial["organization"] = request.GET.get("organization")
    form = CaseForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        case = create_case(
            organization=data["organization"],
            right=data["right"],
            scope=data["scope"],
            priority=data["priority"],
            title=data["title"],
            notes=data["notes"],
            jurisdiction=data["jurisdiction"],
            actor=request.user,
            request=request,
        )
        if data["fees"] is not None:
            case.fees = data["fees"]
            case.save(update_fields=["fees", "updated_at"])
        messages.success(request, f"Case {case.reference} created.")
        return redirect(case)
    return render(
        request,
        "cases/form.html",
        {"form": form, "title": "New case", "case": None},
    )


@login_required
def case_detail(request, pk):
    case = get_object_or_404(Case.objects.select_related("organization"), pk=pk)
    events = case.events.select_related("actor")[:100]
    messages_qs = case.messages.select_related("template")[:50]
    attachments = case.attachments.select_related("message").all()
    tasks = case.tasks.all()
    transition_form = TransitionForm(case=case)
    extend_form = ExtendDeadlineForm(initial={"notice_date": timezone.localdate()})
    task_form = TaskForm()
    attachment_form = AttachmentForm()
    profile = DataSubject.get_primary()

    return render(
        request,
        "cases/detail.html",
        {
            "case": case,
            "events": events,
            "case_messages": messages_qs,
            "attachments": attachments,
            "tasks": tasks,
            "open_tasks": [task for task in tasks if task.status == Task.Status.OPEN],
            "transition_form": transition_form,
            "extend_form": extend_form,
            "task_form": task_form,
            "attachment_form": attachment_form,
            "checklist_items": case.checklist_items,
            "profile": profile,
            "today": timezone.localdate(),
        },
    )


@login_required
def case_update(request, pk):
    case = get_object_or_404(Case, pk=pk)
    previous_right = case.right
    form = CaseForm(request.POST or None, instance=case)
    if request.method == "POST" and form.is_valid():
        case = form.save(commit=False)
        if case.right != previous_right:
            case.checklist = initial_checklist(case.right)
        case.save()
        add_event(
            case,
            CaseEvent.EventType.UPDATED,
            actor=request.user,
            summary="Case details updated",
        )
        log(
            actor=request.user,
            action="case.update",
            entity_type="case",
            entity_id=str(case.pk),
            summary=f"Updated case {case.reference}",
            request=request,
        )
        messages.success(request, "Case updated.")
        return redirect(case)
    return render(
        request,
        "cases/form.html",
        {"form": form, "title": f"Edit {case.reference}", "case": case},
    )


@login_required
@require_POST
def case_transition(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = TransitionForm(request.POST, case=case)
    if form.is_valid():
        try:
            transition_case(
                case,
                form.cleaned_data["status"],
                actor=request.user,
                note=form.cleaned_data["note"],
                request=request,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Status updated.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect(case)


@login_required
@require_POST
def case_extend(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = ExtendDeadlineForm(request.POST)
    if form.is_valid():
        try:
            extend_deadline(
                case,
                notice_date=form.cleaned_data["notice_date"],
                note=form.cleaned_data["note"],
                actor=request.user,
                request=request,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Deadline extended.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect(case)


@login_required
@require_POST
def case_note(request, pk):
    case = get_object_or_404(Case, pk=pk)
    note = request.POST.get("note", "").strip()
    if not note:
        messages.error(request, "Write a note first.")
    else:
        summary = note.splitlines()[0][:120]
        add_event(
            case,
            CaseEvent.EventType.NOTE,
            actor=request.user,
            summary=summary,
            detail=note,
        )
        log(
            actor=request.user,
            action="case.note",
            entity_type="case",
            entity_id=str(case.pk),
            summary=f"Added note to {case.reference}",
            request=request,
        )
        messages.success(request, "Note added to the timeline.")
    return redirect(case)


@login_required
@require_POST
def task_create(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = TaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.case = case
        task.save()
        add_event(
            case,
            CaseEvent.EventType.TASK,
            actor=request.user,
            summary=f"Task added: {task.title}",
            metadata={"task_id": task.pk},
        )
        messages.success(request, "Task added.")
    else:
        messages.error(request, form.errors.as_text())
    return redirect(case)


@login_required
@require_POST
def task_toggle(request, pk, task_pk):
    case = get_object_or_404(Case, pk=pk)
    task = get_object_or_404(Task, pk=task_pk, case=case)
    if task.status == Task.Status.DONE:
        task.status = Task.Status.OPEN
        task.completed_at = None
    else:
        task.status = Task.Status.DONE
        task.completed_at = timezone.now()
    task.save()
    add_event(
        case,
        CaseEvent.EventType.TASK,
        actor=request.user,
        summary=f"Task {'completed' if task.status == Task.Status.DONE else 'reopened'}: {task.title}",
        metadata={"task_id": task.pk},
    )
    if request.headers.get("HX-Request"):
        return render(request, "cases/_task_row.html", {"task": task, "case": case})
    return redirect(case)


@login_required
@require_POST
def checklist_toggle(request, pk):
    case = get_object_or_404(Case, pk=pk)
    key = request.POST.get("key", "")
    valid_keys = {item["key"] for item in checklist_for(case.right)}
    if key not in valid_keys:
        messages.error(request, "Unknown checklist item.")
        return redirect(case)
    state = dict(case.checklist or {})
    state[key] = not bool(state.get(key))
    case.checklist = state
    case.save(update_fields=["checklist", "updated_at"])
    label = next(item["label"] for item in case.checklist_items if item["key"] == key)
    add_event(
        case,
        CaseEvent.EventType.CHECKLIST,
        actor=request.user,
        summary=f"Checklist {'checked' if state[key] else 'unchecked'}: {label}",
    )
    if request.headers.get("HX-Request"):
        return render(
            request,
            "cases/_checklist.html",
            {"case": case, "checklist_items": case.checklist_items},
        )
    return redirect(case)
