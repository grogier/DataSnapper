from __future__ import annotations

from django.db import models
from django.urls import reverse
from django.utils import timezone

from cases.rights import RIGHT_CHOICES, checklist_for, initial_checklist, right_label
from core.models import TimeStampedModel
from core.utils import add_months


class Case(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Ready to send"
        SENT = "sent", "Sent"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        IDENTITY_CHECK = "identity_check", "Identity check"
        IN_PROGRESS = "in_progress", "In progress"
        PARTIALLY_FULFILLED = "partially_fulfilled", "Partially fulfilled"
        FULFILLED = "fulfilled", "Fulfilled"
        REFUSED = "refused", "Refused"
        NO_RESPONSE = "no_response", "No response"
        ESCALATED = "escalated", "Escalated"
        WITHDRAWN = "withdrawn", "Withdrawn"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    class Outcome(models.TextChoices):
        PENDING = "pending", "Pending"
        FULFILLED = "fulfilled", "Fulfilled"
        PARTIALLY_FULFILLED = "partially_fulfilled", "Partially fulfilled"
        REFUSED = "refused", "Refused"
        WITHDRAWN = "withdrawn", "Withdrawn"
        NO_RESPONSE = "no_response", "No response"

    organization = models.ForeignKey(
        "companies.Organization", on_delete=models.PROTECT, related_name="cases"
    )
    reference = models.CharField(max_length=40, unique=True, editable=False)
    right = models.CharField(max_length=40, choices=RIGHT_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    scope = models.TextField(
        blank=True,
        help_text="What the request covers: accounts, services, time period, specific data.",
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    jurisdiction = models.CharField(max_length=40, default="EU")
    opened_at = models.DateField(default=timezone.localdate)
    sent_at = models.DateField(null=True, blank=True)
    received_at = models.DateField(null=True, blank=True)
    due_at = models.DateField(null=True, blank=True)
    extended_due_at = models.DateField(null=True, blank=True)
    extension_notice_at = models.DateField(null=True, blank=True)
    identity_check_at = models.DateField(null=True, blank=True)
    closed_at = models.DateField(null=True, blank=True)
    outcome = models.CharField(max_length=30, choices=Outcome.choices, default=Outcome.PENDING)
    fees = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    checklist = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-opened_at", "-id"]
        indexes = [
            models.Index(fields=["status", "due_at"]),
            models.Index(fields=["right"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.organization.name}"

    def get_absolute_url(self) -> str:
        return reverse("case-detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.reference:
            from cases.services import next_reference
            from core.models import AppSettings

            self.reference = next_reference(AppSettings.load().case_prefix)
        if not self.checklist:
            self.checklist = initial_checklist(self.right)
        if self.sent_at and not self.due_at:
            self.due_at = add_months(self.sent_at, 1)
        super().save(*args, **kwargs)

    @property
    def right_label(self) -> str:
        return right_label(self.right)

    @property
    def effective_due(self):
        return self.extended_due_at or self.due_at

    @property
    def days_left(self) -> int | None:
        if not self.effective_due:
            return None
        return (self.effective_due - timezone.localdate()).days

    @property
    def is_overdue(self) -> bool:
        if not self.effective_due or self.status in {
            self.Status.FULFILLED,
            self.Status.WITHDRAWN,
            self.Status.CLOSED,
        }:
            return False
        return self.effective_due < timezone.localdate()

    @property
    def deadline_tone(self) -> str:
        if not self.effective_due:
            return "none"
        if self.is_overdue:
            return "danger"
        if self.days_left is not None and self.days_left <= 10:
            return "warning"
        return "ok"

    @property
    def is_open(self) -> bool:
        return self.status not in {
            self.Status.FULFILLED,
            self.Status.WITHDRAWN,
            self.Status.CLOSED,
        }

    @property
    def checklist_items(self) -> list[dict]:
        state = self.checklist or {}
        return [
            {
                "key": item["key"],
                "label": item["label"],
                "checked": bool(state.get(item["key"])),
            }
            for item in checklist_for(self.right)
        ]

    @property
    def checklist_done(self) -> int:
        return sum(1 for item in self.checklist_items if item["checked"])

    @property
    def checklist_total(self) -> int:
        return len(self.checklist_items)

    @property
    def checklist_percent(self) -> int:
        total = self.checklist_total
        if not total:
            return 0
        return round(self.checklist_done / total * 100)

    def allowed_transitions(self) -> list[tuple[str, str]]:
        from cases.services import TRANSITIONS

        labels = dict(self.Status.choices)
        return [(value, labels[value]) for value in TRANSITIONS.get(self.status, [])]


class CaseEvent(models.Model):
    class EventType(models.TextChoices):
        CREATED = "created", "Case created"
        UPDATED = "updated", "Case updated"
        STATUS = "status", "Status changed"
        MESSAGE = "message", "Message"
        REPLY = "reply", "Reply received"
        ATTACHMENT = "attachment", "Document added"
        TASK = "task", "Task"
        DEADLINE = "deadline", "Deadline"
        CHECKLIST = "checklist", "Checklist"
        NOTE = "note", "Note"
        EXPORT = "export", "Export"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    actor = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    summary = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.case.reference}: {self.summary}"


class Task(TimeStampedModel):
    class TaskType(models.TextChoices):
        FOLLOW_UP = "follow_up", "Follow-up"
        ESCALATION = "escalation", "Escalation"
        REVIEW = "review", "Review response"
        IDENTITY = "identity", "Identity verification"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    task_type = models.CharField(
        max_length=20, choices=TaskType.choices, default=TaskType.FOLLOW_UP
    )
    due_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-status", "due_at", "id"]

    def __str__(self) -> str:
        return f"{self.title} ({self.case.reference})"

    @property
    def is_overdue(self) -> bool:
        return (
            self.status == self.Status.OPEN
            and self.due_at is not None
            and self.due_at < timezone.localdate()
        )
