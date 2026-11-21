from __future__ import annotations

from django import forms

from companies.models import Contact, DataInventory, Organization
from core.forms import StyledFormMixin


class OrganizationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "legal_name",
            "trading_name",
            "category",
            "status",
            "country",
            "website",
            "privacy_policy_url",
            "privacy_email",
            "dpo_name",
            "dpo_email",
            "phone",
            "postal_address",
            "notes",
        ]
        widgets = {
            "postal_address": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ContactForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Contact
        fields = [
            "name",
            "role",
            "email",
            "phone",
            "postal_address",
            "source",
            "verified_at",
            "notes",
        ]
        widgets = {
            "postal_address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "verified_at": forms.DateInput(attrs={"type": "date"}),
        }


class DataInventoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DataInventory
        fields = [
            "service_name",
            "identifier",
            "data_categories",
            "source",
            "first_seen",
            "notes",
        ]
        widgets = {
            "data_categories": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "first_seen": forms.DateInput(attrs={"type": "date"}),
        }
