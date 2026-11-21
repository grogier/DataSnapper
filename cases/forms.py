from __future__ import annotations

from django import forms

from cases.models import Case, Task
from cases.rights import RIGHT_CHOICES
from companies.models import Organization
from core.forms import StyledFormMixin


class CaseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Case
        fields = [
            "organization",
            "right",
            "title",
            "scope",
            "priority",
            "jurisdiction",
            "notes",
            "fees",
        ]
        widgets = {
            "scope": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Accounts, email addresses, services and time period this request covers."
                    ),
                }
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.order_by("name")
        self.fields["right"].choices = RIGHT_CHOICES


class TransitionForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(choices=[])
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note for the timeline."}),
    )

    def __init__(self, *args, case: Case, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = case.allowed_transitions()


class ExtendDeadlineForm(StyledFormMixin, forms.Form):
    notice_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Date the controller told you about the extension.",
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))


class TaskForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "task_type", "due_at", "notes"]
        widgets = {
            "due_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
