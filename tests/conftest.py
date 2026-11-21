from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.management import call_command

from cases.services import create_case
from companies.models import Contact, Organization
from core.models import DataSubject


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, settings):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    settings.DATA_DIR = data_dir
    settings.MEDIA_ROOT = data_dir / "media"
    settings.MEDIA_ROOT.mkdir()
    settings.BACKUP_DIR = data_dir / "backups"
    settings.BACKUP_DIR.mkdir()
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield


@pytest.fixture(autouse=True)
def isolated_llm_env(monkeypatch):
    for name in (
        "LLM_ENABLED",
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_TIMEOUT",
        "LLM_MAX_OUTPUT_TOKENS",
        "LLM_REASONING",
        "LLM_SHARE_PERSONAL_DATA",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "LLM_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="tester", password="a-long-test-password", is_superuser=True
    )


@pytest.fixture
def client_logged_in(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def profile(db):
    return DataSubject.objects.create(
        full_name="Test Person",
        email="me@example.com",
        postal_address="Teststraat 1\n1234 AB Amsterdam\nNetherlands",
        is_primary=True,
    )


@pytest.fixture
def organization(db):
    org = Organization.objects.create(
        name="Example Corp",
        legal_name="Example Corporation B.V.",
        privacy_email="privacy@example.com",
        postal_address="Main Street 1\n1000 AA Amsterdam",
        country="Netherlands",
    )
    Contact.objects.create(organization=org, role=Contact.Role.PRIVACY, email="privacy@example.com")
    return org


@pytest.fixture
def case(user, organization):
    return create_case(
        organization=organization,
        right="access",
        scope="Account me@example.com and purchase history since 2020.",
        actor=user,
    )


@pytest.fixture
def templates(db):
    call_command("seed_templates")
