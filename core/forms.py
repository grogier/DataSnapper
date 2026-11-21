from __future__ import annotations

from django import forms

from core.models import AppSettings, DataSubject


class StyledFormMixin:
    """Apply consistent classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "checkbox")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "textarea")
                widget.attrs.setdefault("rows", 4)
            else:
                widget.attrs.setdefault("class", "input")


class DataSubjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DataSubject
        fields = ["full_name", "email", "phone", "postal_address", "country", "notes"]
        widgets = {
            "postal_address": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Street and number\nPostal code and city\nCountry"}
            ),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class AppSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = ["case_prefix", "default_locale", "reminder_days", "retention_days"]
        help_texts = {
            "reminder_days": "Example: 10,3,0. Reminders appear on the dashboard and in the calendar.",
            "retention_days": "0 keeps everything. A positive value enables the purge command.",
        }

    def clean_case_prefix(self):
        value = self.cleaned_data["case_prefix"].strip().upper()
        if not value.replace("-", "").isalnum():
            raise forms.ValidationError("Use letters, numbers or a dash.")
        return value
