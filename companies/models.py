from __future__ import annotations

from django.db import models
from django.urls import reverse

from core.models import TimeStampedModel


class Organization(TimeStampedModel):
    class Category(models.TextChoices):
        COMPANY = "company", "Company"
        DATA_BROKER = "data_broker", "Data broker"
        PUBLIC_BODY = "public_body", "Public body"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ERASED = "erased", "Erased"
        BLOCKED = "blocked", "Blocked / do not contact"
        ARCHIVED = "archived", "Archived"

    name = models.CharField(max_length=200, help_text="Name you recognise, e.g. the brand.")
    legal_name = models.CharField(max_length=200, blank=True)
    trading_name = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.COMPANY)
    country = models.CharField(max_length=100, blank=True, default="Netherlands")
    website = models.URLField(blank=True)
    privacy_policy_url = models.URLField(blank=True)
    privacy_email = models.EmailField(blank=True, help_text="General privacy contact.")
    dpo_name = models.CharField(max_length=200, blank=True)
    dpo_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    postal_address = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "organisation"
        verbose_name_plural = "organisations"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("organization-detail", args=[self.pk])

    @property
    def display_name(self) -> str:
        return self.legal_name or self.name

    @property
    def primary_contact(self) -> Contact | None:
        contacts = list(self.contacts.all())
        for contact in contacts:
            if contact.role == Contact.Role.PRIVACY:
                return contact
        return contacts[0] if contacts else None

    @property
    def best_email(self) -> str:
        contact = self.primary_contact
        if contact and contact.email:
            return contact.email
        return self.dpo_email or self.privacy_email


class Contact(TimeStampedModel):
    class Role(models.TextChoices):
        PRIVACY = "privacy", "Privacy team"
        DPO = "dpo", "Data protection officer"
        LEGAL = "legal", "Legal"
        SUPPORT = "support", "Customer support"
        OTHER = "other", "Other"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="contacts"
    )
    name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PRIVACY)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    postal_address = models.TextField(blank=True)
    source = models.CharField(
        max_length=200, blank=True, help_text="Where you found this contact, e.g. privacy policy."
    )
    verified_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["role", "name", "pk"]

    def __str__(self) -> str:
        return f"{self.name or self.get_role_display()} ({self.organization.name})"


class DataInventory(TimeStampedModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="inventory"
    )
    service_name = models.CharField(max_length=200, help_text="Product, account or service.")
    identifier = models.CharField(
        max_length=200, blank=True, help_text="Email address, username or customer number."
    )
    data_categories = models.TextField(
        blank=True, help_text="What you believe they hold: account, purchases, location, ..."
    )
    source = models.CharField(max_length=200, blank=True)
    first_seen = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["service_name"]
        verbose_name = "data inventory entry"
        verbose_name_plural = "data inventory"

    def __str__(self) -> str:
        return f"{self.service_name} — {self.organization.name}"
