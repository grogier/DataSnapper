"""GDPR request types and the response checklist used by the case file."""

from __future__ import annotations

RIGHTS: dict[str, dict] = {
    "access": {
        "label": "Access / copy of data",
        "short": "Access",
        "article": "Art. 15 GDPR",
        "description": (
            "Ask whether your data is processed and receive a copy, together with the "
            "purposes, categories, recipients, retention, source and safeguards."
        ),
        "checklist": [
            ("confirmation", "Confirmation that data is processed"),
            ("purposes", "Purposes of processing"),
            ("categories", "Categories of personal data"),
            ("recipients", "Recipients or categories of recipients"),
            ("retention", "Retention periods"),
            ("rights", "Information about your rights"),
            ("source", "Source of the data"),
            ("automated", "Automated decision-making explained"),
            ("transfers", "International transfers and safeguards"),
            ("copy", "Copy of the personal data received"),
        ],
    },
    "rectification": {
        "label": "Rectification",
        "short": "Rectification",
        "article": "Art. 16 GDPR",
        "description": "Ask for inaccurate or incomplete personal data to be corrected.",
        "checklist": [
            ("disputed", "Inaccurate fields identified"),
            ("evidence", "Supporting evidence attached"),
            ("confirmation", "Correction confirmed"),
            ("recipients", "Recipients informed of the correction"),
        ],
    },
    "erasure": {
        "label": "Erasure (right to be forgotten)",
        "short": "Erasure",
        "article": "Art. 17 GDPR",
        "description": "Ask for personal data to be deleted where there is no good reason to keep it.",
        "checklist": [
            ("scope", "Data and systems covered"),
            ("exemptions", "Any exemption claimed by the controller"),
            ("confirmation", "Deletion confirmed"),
            ("recipients", "Recipients informed of the deletion"),
            ("backups", "Backup deletion or retention explained"),
        ],
    },
    "restriction": {
        "label": "Restriction of processing",
        "short": "Restriction",
        "article": "Art. 18 GDPR",
        "description": "Ask the controller to restrict processing while accuracy or lawfulness is disputed.",
        "checklist": [
            ("scope", "Processing restricted and how"),
            ("confirmation", "Restriction confirmed"),
            ("duration", "Expected duration or review date"),
        ],
    },
    "portability": {
        "label": "Data portability",
        "short": "Portability",
        "article": "Art. 20 GDPR",
        "description": "Receive data you provided in a structured, machine-readable format.",
        "checklist": [
            ("format", "Machine-readable format received"),
            ("scope", "Provided data versus derived data explained"),
            ("transfer", "Transfer to another controller completed, if requested"),
        ],
    },
    "objection": {
        "label": "Objection to processing",
        "short": "Objection",
        "article": "Art. 21 GDPR",
        "description": "Object to processing based on legitimate interests or direct marketing.",
        "checklist": [
            ("purpose", "Processing purpose objected to"),
            ("confirmation", "Processing stopped or compelling grounds given"),
            ("marketing", "Direct marketing opt-out confirmed"),
        ],
    },
    "consent_withdrawal": {
        "label": "Withdraw consent",
        "short": "Consent",
        "article": "Art. 7(3) GDPR",
        "description": "Withdraw consent for processing that relies on it.",
        "checklist": [
            ("purpose", "Consent and purpose identified"),
            ("confirmation", "Withdrawal confirmed"),
            ("consequences", "Consequences explained"),
        ],
    },
    "automated_decision": {
        "label": "Automated decision-making",
        "short": "Automated decision",
        "article": "Art. 22 GDPR",
        "description": "Ask for a meaningful explanation of automated decisions and human review.",
        "checklist": [
            ("logic", "Meaningful explanation of the logic"),
            ("consequences", "Envisaged consequences explained"),
            ("human_review", "Human intervention requested"),
            ("contest", "Decision contested"),
        ],
    },
    "source": {
        "label": "Source, recipients and retention",
        "short": "Source",
        "article": "Art. 14 and 15 GDPR",
        "description": "Ask where data came from, who received it and how long it is kept.",
        "checklist": [
            ("source", "Source of the data"),
            ("recipients", "Recipients or categories of recipients"),
            ("transfers", "International transfers and safeguards"),
            ("retention", "Retention periods"),
        ],
    },
    "evidence": {
        "label": "Evidence of lawful basis or deletion",
        "short": "Evidence",
        "article": "Accountability, Art. 5(2) and 7(1) GDPR",
        "description": (
            "Ask for evidence of the lawful basis, consent, or deletion. This is an "
            "accountability request, not a separate data-subject right."
        ),
        "checklist": [
            ("lawful_basis", "Lawful basis stated"),
            ("proof", "Evidence or documentation provided"),
            ("deletion_proof", "Proof of deletion, if applicable"),
            ("consent_proof", "Consent record, if applicable"),
        ],
    },
}

RIGHT_CHOICES = [(key, value["label"]) for key, value in RIGHTS.items()]


def right_definition(key: str) -> dict | None:
    return RIGHTS.get(key)


def right_label(key: str) -> str:
    definition = right_definition(key)
    return definition["label"] if definition else key


def checklist_for(key: str) -> list[dict[str, str]]:
    definition = right_definition(key)
    if not definition:
        return []
    return [{"key": item[0], "label": item[1]} for item in definition["checklist"]]


def initial_checklist(key: str) -> dict[str, bool]:
    return {item["key"]: False for item in checklist_for(key)}
