import pytest
from django.urls import reverse

from cases.models import Case
from companies.models import Organization


@pytest.mark.django_db
def test_login_required(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert reverse("login") in response.url
    assert client.get(reverse("login")).status_code == 200
    assert client.get(reverse("health")).status_code == 200


@pytest.mark.django_db
def test_main_pages_render(client_logged_in, case, organization, profile, templates):
    urls = [
        reverse("dashboard"),
        reverse("case-list"),
        reverse("case-detail", args=[case.pk]),
        reverse("case-create"),
        reverse("case-update", args=[case.pk]),
        reverse("case-compose", args=[case.pk]),
        reverse("case-reply", args=[case.pk]),
        reverse("organization-list"),
        reverse("organization-detail", args=[organization.pk]),
        reverse("organization-create"),
        reverse("organization-update", args=[organization.pk]),
        reverse("contact-create", args=[organization.pk]),
        reverse("inventory-create", args=[organization.pk]),
        reverse("template-list"),
        reverse("template-create"),
        reverse("evidence-list"),
        reverse("evidence-upload"),
        reverse("calendar"),
        reverse("calendar-ics"),
        reverse("settings"),
        reverse("audit-list"),
        reverse("search") + "?q=example",
    ]
    for url in urls:
        response = client_logged_in.get(url)
        assert response.status_code == 200, url


@pytest.mark.django_db
def test_create_company_and_case_through_views(client_logged_in, profile):
    response = client_logged_in.post(
        reverse("organization-create"),
        {
            "name": "New Co",
            "category": "company",
            "status": "active",
            "country": "Netherlands",
        },
    )
    assert response.status_code == 302
    organization = Organization.objects.get(name="New Co")

    response = client_logged_in.post(
        reverse("case-create"),
        {
            "organization": organization.pk,
            "right": "access",
            "title": "My request",
            "scope": "Everything.",
            "priority": "normal",
            "jurisdiction": "EU",
        },
    )
    assert response.status_code == 302
    case = Case.objects.get(organization=organization)
    assert case.reference.startswith("DSAR-")
    assert case.status == Case.Status.DRAFT


@pytest.mark.django_db
def test_transition_view(client_logged_in, case):
    response = client_logged_in.post(
        reverse("case-transition", args=[case.pk]),
        {"status": "sent", "note": "Posted today."},
    )
    assert response.status_code == 302
    case.refresh_from_db()
    assert case.status == Case.Status.SENT
    assert case.due_at is not None


@pytest.mark.django_db
def test_checklist_toggle_htmx(client_logged_in, case):
    response = client_logged_in.post(
        reverse("checklist-toggle", args=[case.pk]),
        {"key": "purposes"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    case.refresh_from_db()
    assert case.checklist["purposes"] is True
    assert b"checklist-panel" in response.content
