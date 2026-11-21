import pytest

from cases.models import Case
from cases.services import transition_case
from correspondence.models import Template
from correspondence.services import build_letter_context


@pytest.mark.django_db
def test_seed_templates_are_english_and_dutch(templates):
    assert Template.objects.count() == 20
    assert Template.objects.filter(locale="en").count() == 10
    assert Template.objects.filter(locale="nl").count() == 10
    assert Template.objects.filter(is_active=True).count() == 20


@pytest.mark.django_db
def test_english_access_letter_renders(case, profile, templates, user):
    transition_case(case, Case.Status.SENT, actor=user)
    case.refresh_from_db()
    template = Template.objects.get(slug="access-request", locale="en", version=1)
    context = build_letter_context(case, template)
    subject, body = template.render(context)

    assert case.reference in subject
    assert "Article 15" in body
    assert "Test Person" in body
    assert "Account me@example.com" in body
    assert "{{" not in body
    assert "Example Corp" not in body  # the body is addressed to the company, not about it
    assert "one month" in body


@pytest.mark.django_db
def test_dutch_erasure_letter_renders(case, profile, templates):
    case.right = "erasure"
    case.save()
    template = Template.objects.get(slug="erasure-request", locale="nl", version=1)
    context = build_letter_context(case, template, scope="Mijn account en bestelgeschiedenis.")
    subject, body = template.render(context)

    assert "AVG" in subject
    assert "artikel 17" in body
    assert "Mijn account en bestelgeschiedenis." in body
    assert "Met vriendelijke groet" in body
    assert "{{" not in body


@pytest.mark.django_db
def test_missing_variables_are_detected(case, profile, templates):
    from correspondence.services import missing_for_template

    template = Template.objects.get(slug="access-request", locale="en", version=1)
    context = build_letter_context(case, template)
    assert missing_for_template(template, context) == []
    assert missing_for_template(template, {"profile": {}}) != []
