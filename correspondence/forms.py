from __future__ import annotations

from django import forms
from django.conf import settings

from cases.models import Case
from core.forms import StyledFormMixin
from core.models import AppSettings
from correspondence.models import Attachment, Message, Template

TONES = (("neutral", "Neutral"), ("firm", "Firm"))
LENGTHS = (("concise", "Concise"), ("thorough", "Thorough"))


class ComposeForm(StyledFormMixin, forms.Form):
    """One form for both the AI-first and the template-only path."""

    template = forms.ModelChoiceField(
        queryset=Template.objects.none(),
        required=False,
        label="Base template",
        help_text="Sets the language, structure and legal wording. AI adapts it to this case.",
    )
    to_address = forms.CharField(required=False, max_length=320, label="Send to")
    scope = forms.CharField(
        required=False,
        label="Scope",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Name the accounts, email addresses, services and period to cover.",
    )
    extra_note = forms.CharField(
        required=False,
        label="Anything specific to mention?",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "Example: mention my old account and the marketing emails I still receive."
                ),
            }
        ),
        help_text="Used by the AI and added to the letter when you use the template.",
    )
    tone = forms.ChoiceField(choices=TONES, initial="neutral", required=False)
    length = forms.ChoiceField(choices=LENGTHS, initial="concise", required=False)
    reasoning = forms.BooleanField(
        required=False,
        label="Reasoning mode (slower, better for complex requests)",
    )

    def __init__(self, *args, case: Case, include_ai_options: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        templates = Template.objects.filter(right=case.right, is_active=True).order_by(
            "locale", "name", "-version"
        )
        self.fields["template"].queryset = templates
        self.fields["template"].empty_label = "No template (draft from scratch)"
        self.fields["to_address"].initial = case.organization.best_email
        self.fields["scope"].initial = case.scope
        if not include_ai_options:
            for name in ("tone", "length", "reasoning"):
                self.fields.pop(name, None)
        if not self.is_bound:
            locale = AppSettings.load().default_locale
            preferred = templates.filter(locale=locale).first() or templates.first()
            if preferred is not None:
                self.fields["template"].initial = preferred.pk


class ReplyForm(StyledFormMixin, forms.Form):
    channel = forms.ChoiceField(choices=Message.Channel.choices, initial=Message.Channel.EMAIL)
    from_address = forms.CharField(max_length=320, required=False)
    subject = forms.CharField(max_length=255)
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 8}))
    received_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    mark_acknowledged = forms.BooleanField(
        required=False,
        initial=True,
        label="Move case to Acknowledged if possible",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["received_at"].input_formats = ["%Y-%m-%dT%H:%M"]


class AttachmentForm(StyledFormMixin, forms.Form):
    kind = forms.ChoiceField(choices=Attachment.Kind.choices, initial=Attachment.Kind.OTHER)
    file = forms.FileField()
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        limit = settings.FILE_UPLOAD_MAX_MEMORY_SIZE
        if uploaded.size > limit:
            raise forms.ValidationError(
                f"File is larger than the {limit // (1024 * 1024)} MB limit."
            )
        return uploaded


class EvidenceUploadForm(StyledFormMixin, forms.Form):
    case = forms.ModelChoiceField(queryset=Case.objects.order_by("-opened_at"), required=False)
    kind = forms.ChoiceField(choices=Attachment.Kind.choices, initial=Attachment.Kind.OTHER)
    file = forms.FileField()
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        limit = settings.FILE_UPLOAD_MAX_MEMORY_SIZE
        if uploaded.size > limit:
            raise forms.ValidationError(
                f"File is larger than the {limit // (1024 * 1024)} MB limit."
            )
        return uploaded


class TemplateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Template
        fields = [
            "slug",
            "name",
            "right",
            "jurisdiction",
            "locale",
            "subject",
            "body",
            "legal_refs",
            "notes",
        ]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 18, "class": "textarea code"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["slug"].disabled = True
