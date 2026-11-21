from __future__ import annotations

from django import forms

from core.llm.providers import provider_spec
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


class LLMSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = [
            "llm_enabled",
            "llm_provider",
            "llm_base_url",
            "llm_model",
            "llm_timeout",
            "llm_max_output_tokens",
            "llm_reasoning",
            "llm_share_personal_data",
        ]
        labels = {
            "llm_enabled": "Enable AI assistance",
            "llm_provider": "Provider",
            "llm_base_url": "Base URL",
            "llm_model": "Model",
            "llm_timeout": "Timeout (seconds)",
            "llm_max_output_tokens": "Maximum output tokens",
            "llm_reasoning": "Use reasoning / thinking mode",
            "llm_share_personal_data": "Share personal data with the LLM",
        }
        help_texts = {
            "llm_base_url": (
                "Ollama on the host: http://host.docker.internal:11434. "
                "Ollama as a Compose service: http://ollama:11434."
            ),
            "llm_reasoning": "Slower, but better for complex requests. Only used by providers "
            "that support thinking mode. Raise the output limit if reasoning uses too many tokens.",
            "llm_share_personal_data": (
                "Off keeps names, addresses and contact details out of the prompt. "
                "The letter still uses placeholders that are filled in locally."
            ),
        }

    def clean_llm_base_url(self):
        value = (self.cleaned_data.get("llm_base_url") or "").strip().rstrip("/")
        if not value:
            return value
        if not (value.startswith("http://") or value.startswith("https://")):
            raise forms.ValidationError("Use an http:// or https:// URL.")
        return value

    def clean_llm_timeout(self):
        value = self.cleaned_data.get("llm_timeout") or 120
        if not 5 <= value <= 600:
            raise forms.ValidationError("Use a timeout between 5 and 600 seconds.")
        return value

    def clean_llm_max_output_tokens(self):
        value = self.cleaned_data.get("llm_max_output_tokens") or 1500
        if not 100 <= value <= 8000:
            raise forms.ValidationError("Use between 100 and 8000 tokens.")
        return value

    def clean(self):
        cleaned = super().clean()
        provider = cleaned.get("llm_provider") or AppSettings.LLMProvider.OLLAMA
        spec = provider_spec(provider)
        previous = self.initial.get("llm_provider") or ""
        previous_spec = provider_spec(previous) if previous else None

        base_url = cleaned.get("llm_base_url") or ""
        if not base_url:
            base_url = spec.default_base_url
        elif previous_spec and provider != previous:
            if base_url.rstrip("/") == previous_spec.default_base_url:
                base_url = spec.default_base_url
        cleaned["llm_base_url"] = base_url.rstrip("/")

        model = (cleaned.get("llm_model") or "").strip()
        if not model:
            model = spec.default_model
        elif previous_spec and provider != previous and model == previous_spec.default_model:
            model = spec.default_model
        cleaned["llm_model"] = model
        return cleaned
