from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from audit.services import log
from companies.forms import ContactForm, DataInventoryForm, OrganizationForm
from companies.models import Contact, DataInventory, Organization


@login_required
def organization_list(request):
    organizations = Organization.objects.annotate(case_count=Count("cases")).order_by("name")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    status = request.GET.get("status", "")
    if query:
        organizations = organizations.filter(
            Q(name__icontains=query)
            | Q(legal_name__icontains=query)
            | Q(trading_name__icontains=query)
            | Q(privacy_email__icontains=query)
            | Q(dpo_email__icontains=query)
        )
    if category:
        organizations = organizations.filter(category=category)
    if status:
        organizations = organizations.filter(status=status)

    paginator = Paginator(organizations, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "companies/list.html",
        {
            "page": page,
            "organizations": page.object_list,
            "query": query,
            "category": category,
            "status": status,
            "categories": Organization.Category.choices,
            "statuses": Organization.Status.choices,
            "total": paginator.count,
        },
    )


@login_required
def organization_detail(request, pk):
    organization = get_object_or_404(
        Organization.objects.prefetch_related("contacts", "inventory"), pk=pk
    )
    cases = organization.cases.select_related("organization").order_by("-opened_at")[:20]
    recent_messages = (
        organization.cases.filter(messages__isnull=False)
        .values(
            "messages__pk",
            "messages__subject",
            "messages__direction",
            "messages__created_at",
            "reference",
            "pk",
        )
        .order_by("-messages__created_at")[:10]
    )
    return render(
        request,
        "companies/detail.html",
        {
            "organization": organization,
            "cases": cases,
            "recent_messages": recent_messages,
        },
    )


@login_required
def organization_create(request):
    form = OrganizationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        organization = form.save()
        log(
            actor=request.user,
            action="organization.create",
            entity_type="organization",
            entity_id=str(organization.pk),
            summary=f"Created organisation {organization.name}",
            request=request,
        )
        messages.success(request, "Organisation created.")
        return redirect(organization)
    return render(
        request,
        "companies/form.html",
        {"form": form, "title": "New organisation", "organization": None},
    )


@login_required
def organization_update(request, pk):
    organization = get_object_or_404(Organization, pk=pk)
    form = OrganizationForm(request.POST or None, instance=organization)
    if request.method == "POST" and form.is_valid():
        organization = form.save()
        log(
            actor=request.user,
            action="organization.update",
            entity_type="organization",
            entity_id=str(organization.pk),
            summary=f"Updated organisation {organization.name}",
            request=request,
        )
        messages.success(request, "Organisation updated.")
        return redirect(organization)
    return render(
        request,
        "companies/form.html",
        {"form": form, "title": f"Edit {organization.name}", "organization": organization},
    )


@login_required
def organization_delete(request, pk):
    organization = get_object_or_404(Organization, pk=pk)
    if request.method == "POST":
        if organization.cases.exists():
            messages.error(
                request,
                "This organisation still has cases. Close or delete those cases first.",
            )
            return redirect(organization)
        name = organization.name
        organization.delete()
        log(
            actor=request.user,
            action="organization.delete",
            entity_type="organization",
            entity_id=str(pk),
            summary=f"Deleted organisation {name}",
            request=request,
        )
        messages.success(request, f"Organisation {name} deleted.")
        return redirect("organization-list")
    return render(request, "companies/confirm_delete.html", {"organization": organization})


@login_required
def contact_create(request, pk):
    organization = get_object_or_404(Organization, pk=pk)
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.organization = organization
        contact.save()
        log(
            actor=request.user,
            action="contact.create",
            entity_type="contact",
            entity_id=str(contact.pk),
            summary=f"Added contact to {organization.name}",
            request=request,
        )
        messages.success(request, "Contact added.")
        return redirect(organization)
    return render(
        request,
        "companies/contact_form.html",
        {"form": form, "organization": organization, "title": "Add contact"},
    )


@login_required
def contact_update(request, pk, contact_pk):
    organization = get_object_or_404(Organization, pk=pk)
    contact = get_object_or_404(Contact, pk=contact_pk, organization=organization)
    form = ContactForm(request.POST or None, instance=contact)
    if request.method == "POST" and form.is_valid():
        form.save()
        log(
            actor=request.user,
            action="contact.update",
            entity_type="contact",
            entity_id=str(contact.pk),
            summary=f"Updated contact for {organization.name}",
            request=request,
        )
        messages.success(request, "Contact updated.")
        return redirect(organization)
    return render(
        request,
        "companies/contact_form.html",
        {"form": form, "organization": organization, "title": "Edit contact"},
    )


@login_required
@require_POST
def contact_delete(request, pk, contact_pk):
    organization = get_object_or_404(Organization, pk=pk)
    contact = get_object_or_404(Contact, pk=contact_pk, organization=organization)
    contact.delete()
    log(
        actor=request.user,
        action="contact.delete",
        entity_type="contact",
        entity_id=str(contact_pk),
        summary=f"Deleted contact for {organization.name}",
        request=request,
    )
    messages.success(request, "Contact deleted.")
    return redirect(organization)


@login_required
def inventory_create(request, pk):
    organization = get_object_or_404(Organization, pk=pk)
    form = DataInventoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.organization = organization
        entry.save()
        log(
            actor=request.user,
            action="inventory.create",
            entity_type="data_inventory",
            entity_id=str(entry.pk),
            summary=f"Added data inventory entry for {organization.name}",
            request=request,
        )
        messages.success(request, "Data inventory entry added.")
        return redirect(organization)
    return render(
        request,
        "companies/inventory_form.html",
        {"form": form, "organization": organization, "title": "Add data inventory entry"},
    )


@login_required
@require_POST
def inventory_delete(request, pk, entry_pk):
    organization = get_object_or_404(Organization, pk=pk)
    entry = get_object_or_404(DataInventory, pk=entry_pk, organization=organization)
    entry.delete()
    log(
        actor=request.user,
        action="inventory.delete",
        entity_type="data_inventory",
        entity_id=str(entry_pk),
        summary=f"Deleted data inventory entry for {organization.name}",
        request=request,
    )
    messages.success(request, "Data inventory entry deleted.")
    return redirect(organization)
