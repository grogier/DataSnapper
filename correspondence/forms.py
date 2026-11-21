from __future__ import annotations

from django import forms
from django.conf import settings

from cases.models import Case
from core.forms import StyledFormMixin
from correspondence.models import Attachment, Message, Template


class ComposeForm(StyledFormMixin, forms.Form):
    template = forms.ModelChoiceField(queryset=Template.objects.none())
    to_address = forms.CharField(required=False, max_length=320)
    scope = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    extra_note = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 3, "placeholder": "Optional paragraph added to the letter."}
        ),
    )

    def __init__(self, *args, case: Case, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = Template.objects.filter(
            right=case.right, is_active=True
        ).order_by("locale", "name", "-version")
        self.fields["to_address"].initial = case.organization.best_email
        self.fields["scope"].initial = case.scope


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
