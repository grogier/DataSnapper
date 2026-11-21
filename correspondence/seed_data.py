"""Built-in English and Dutch letter templates.

These are starting points, not legal advice. They deliberately cite the GDPR only
and avoid country-specific statutes so they can be adapted per controller.
"""

from __future__ import annotations

DEADLINE_EN = (
    "You must respond without undue delay and in any event within one month of receipt "
    "of this request (Article 12(3) GDPR). If you need to extend this period by up to two "
    "further months, please inform me within one month of receipt and explain the reasons."
)
IDENTITY_EN = (
    "If you need to verify my identity, please tell me exactly which additional information "
    "you need. Please do not request more than necessary."
)
CLOSING_EN = (
    "Please send your response to {{ profile.email }}"
    "{% if profile.postal_address %} or to the postal address below{% endif %}.\n\n"
    "Yours faithfully,\n"
    "{{ profile.full_name }}\n"
    "{{ profile.postal_address }}\n"
    "{{ profile.email }}"
)

DEADLINE_NL = (
    "U dient zonder onnodige vertraging en in ieder geval binnen één maand na ontvangst van "
    "dit verzoek te reageren (artikel 12, lid 3, AVG). Als u deze termijn met maximaal twee "
    "maanden wilt verlengen, verzoek ik u mij binnen één maand na ontvangst te informeren en "
    "de redenen te vermelden."
)
IDENTITY_NL = (
    "Als u mijn identiteit wilt verifiëren, laat mij dan precies weten welke aanvullende "
    "gegevens u nodig heeft. Vraag niet meer dan noodzakelijk."
)
CLOSING_NL = (
    "U kunt uw reactie sturen naar {{ profile.email }}"
    "{% if profile.postal_address %} of naar het onderstaande postadres{% endif %}.\n\n"
    "Met vriendelijke groet,\n"
    "{{ profile.full_name }}\n"
    "{{ profile.postal_address }}\n"
    "{{ profile.email }}"
)


def body_en(article: str, ask: str, bullets: list[str]) -> str:
    lines = [
        "Dear Sir or Madam,",
        "",
        f"I am writing to exercise my rights under {article} of the General Data "
        "Protection Regulation (GDPR).",
        "",
        "This request concerns: {{ case.scope_text }}.",
        "",
        ask,
        "",
    ]
    lines.extend(f"- {item}" for item in bullets)
    lines.extend(
        [
            "",
            "{% if extra_note %}{{ extra_note }}",
            "",
            "{% endif %}",
            DEADLINE_EN,
            "",
            IDENTITY_EN,
            "",
            CLOSING_EN,
        ]
    )
    return "\n".join(lines)


def body_nl(article: str, ask: str, bullets: list[str]) -> str:
    lines = [
        "Geachte heer, mevrouw,",
        "",
        f"Hierbij doe ik een beroep op mijn rechten op grond van {article} van de "
        "Algemene verordening gegevensbescherming (AVG).",
        "",
        "Dit verzoek betreft: {{ case.scope_text }}.",
        "",
        ask,
        "",
    ]
    lines.extend(f"- {item}" for item in bullets)
    lines.extend(
        [
            "",
            "{% if extra_note %}{{ extra_note }}",
            "",
            "{% endif %}",
            DEADLINE_NL,
            "",
            IDENTITY_NL,
            "",
            CLOSING_NL,
        ]
    )
    return "\n".join(lines)


SEED_TEMPLATES: list[dict] = [
    {
        "slug": "access-request",
        "name": "Access request",
        "right": "access",
        "locale": "en",
        "subject": "GDPR access request — {{ case.reference }}",
        "body": body_en(
            "Article 15",
            "Please provide me with:",
            [
                "the purposes of the processing;",
                "the categories of personal data concerned;",
                "the recipients or categories of recipients to whom the data has been or will be disclosed;",
                "the envisaged retention period, or the criteria used to determine it;",
                "information about my rights to rectification, erasure, restriction and objection;",
                "information about my right to lodge a complaint with a supervisory authority;",
                "the source of the data, where it did not come from me;",
                "the existence of automated decision-making, including meaningful information about the logic, significance and envisaged consequences;",
                "the safeguards for transfers outside the European Economic Area;",
                "a copy of the personal data undergoing processing.",
            ],
        ),
        "legal_refs": "Art. 15, 12 GDPR",
    },
    {
        "slug": "access-request",
        "name": "Inzageverzoek",
        "right": "access",
        "locale": "nl",
        "subject": "AVG-verzoek inzage — {{ case.reference }}",
        "body": body_nl(
            "artikel 15",
            "Ik verzoek u mij de volgende informatie te verstrekken:",
            [
                "de doeleinden van de verwerking;",
                "de categorieën van persoonsgegevens;",
                "de ontvangers of categorieën van ontvangers aan wie de gegevens zijn of zullen worden verstrekt;",
                "de bewaartermijn of de criteria om die te bepalen;",
                "informatie over mijn rechten op rectificatie, wissing, beperking en bezwaar;",
                "informatie over mijn recht om een klacht in te dienen bij een toezichthoudende autoriteit;",
                "de bron van de gegevens, als die niet van mij afkomstig zijn;",
                "het bestaan van geautomatiseerde besluitvorming, met zinvolle informatie over de logica, betekenis en gevolgen;",
                "de waarborgen bij doorgifte buiten de Europese Economische Ruimte;",
                "een kopie van de persoonsgegevens die worden verwerkt.",
            ],
        ),
        "legal_refs": "Art. 15, 12 AVG",
    },
    {
        "slug": "rectification-request",
        "name": "Rectification request",
        "right": "rectification",
        "locale": "en",
        "subject": "GDPR rectification request — {{ case.reference }}",
        "body": body_en(
            "Article 16",
            "Please correct the inaccurate or incomplete personal data described above.",
            [
                "confirm the correction in writing;",
                "inform the recipients of the data about the correction (Article 19 GDPR);",
                "if you consider the data to be accurate, explain why and provide the evidence you rely on.",
            ],
        ),
        "legal_refs": "Art. 16, 19, 12 GDPR",
    },
    {
        "slug": "rectification-request",
        "name": "Rectificatieverzoek",
        "right": "rectification",
        "locale": "nl",
        "subject": "AVG-verzoek rectificatie — {{ case.reference }}",
        "body": body_nl(
            "artikel 16",
            "Ik verzoek u de onjuiste of onvolledige persoonsgegevens die hierboven zijn beschreven te corrigeren.",
            [
                "bevestig de correctie schriftelijk;",
                "informeer de ontvangers van de gegevens over de correctie (artikel 19 AVG);",
                "als u de gegevens juist acht, leg dan uit waarom en verstrek de onderbouwing waarop u zich baseert.",
            ],
        ),
        "legal_refs": "Art. 16, 19, 12 AVG",
    },
    {
        "slug": "erasure-request",
        "name": "Erasure request",
        "right": "erasure",
        "locale": "en",
        "subject": "GDPR erasure request — {{ case.reference }}",
        "body": body_en(
            "Article 17",
            "Please erase the personal data described above without undue delay.",
            [
                "delete the data from all systems and backups, or explain the backup retention;",
                "inform recipients to whom the data was disclosed (Article 19 GDPR);",
                "confirm the deletion in writing;",
                "if you rely on an exemption in Article 17(3) GDPR, identify it and explain why it applies.",
            ],
        ),
        "legal_refs": "Art. 17, 19, 12 GDPR",
    },
    {
        "slug": "erasure-request",
        "name": "Verzoek tot wissing",
        "right": "erasure",
        "locale": "nl",
        "subject": "AVG-verzoek tot wissing — {{ case.reference }}",
        "body": body_nl(
            "artikel 17",
            "Ik verzoek u de hierboven beschreven persoonsgegevens zonder onnodige vertraging te wissen.",
            [
                "verwijder de gegevens uit alle systemen en back-ups, of leg uit hoe lang back-ups worden bewaard;",
                "informeer ontvangers aan wie de gegevens zijn verstrekt (artikel 19 AVG);",
                "bevestig de wissing schriftelijk;",
                "als u een uitzondering op grond van artikel 17, lid 3, AVG toepast, benoem deze dan en leg uit waarom.",
            ],
        ),
        "legal_refs": "Art. 17, 19, 12 AVG",
    },
    {
        "slug": "restriction-request",
        "name": "Restriction request",
        "right": "restriction",
        "locale": "en",
        "subject": "GDPR restriction request — {{ case.reference }}",
        "body": body_en(
            "Article 18",
            "Please restrict the processing of the personal data described above.",
            [
                "confirm the restriction and explain how it is implemented;",
                "state how long the restriction will last;",
                "inform recipients of the restriction (Article 19 GDPR);",
                "do not delete the data while the restriction applies.",
            ],
        ),
        "legal_refs": "Art. 18, 19, 12 GDPR",
    },
    {
        "slug": "restriction-request",
        "name": "Verzoek tot beperking",
        "right": "restriction",
        "locale": "nl",
        "subject": "AVG-verzoek tot beperking — {{ case.reference }}",
        "body": body_nl(
            "artikel 18",
            "Ik verzoek u de verwerking van de hierboven beschreven persoonsgegevens te beperken.",
            [
                "bevestig de beperking en leg uit hoe deze wordt uitgevoerd;",
                "geef aan hoe lang de beperking duurt;",
                "informeer ontvangers over de beperking (artikel 19 AVG);",
                "verwijder de gegevens niet zolang de beperking geldt.",
            ],
        ),
        "legal_refs": "Art. 18, 19, 12 AVG",
    },
    {
        "slug": "portability-request",
        "name": "Portability request",
        "right": "portability",
        "locale": "en",
        "subject": "GDPR portability request — {{ case.reference }}",
        "body": body_en(
            "Article 20",
            "Please provide the personal data I provided to you in a structured, commonly used and machine-readable format.",
            [
                "use a format such as JSON or CSV;",
                "include the data I provided, such as account details, activity and content;",
                "where technically feasible, transmit the data directly to another controller at my request;",
                "confirm which data is included and which is not.",
            ],
        ),
        "legal_refs": "Art. 20, 12 GDPR",
    },
    {
        "slug": "portability-request",
        "name": "Verzoek tot overdraagbaarheid",
        "right": "portability",
        "locale": "nl",
        "subject": "AVG-verzoek gegevensoverdraagbaarheid — {{ case.reference }}",
        "body": body_nl(
            "artikel 20",
            "Ik verzoek u de persoonsgegevens die ik aan u heb verstrekt, te verstrekken in een gestructureerd, algemeen gebruikt en machineleesbaar formaat.",
            [
                "gebruik een formaat zoals JSON of CSV;",
                "neem de gegevens op die ik heb verstrekt, zoals accountgegevens, activiteit en inhoud;",
                "verstrek de gegevens waar technisch mogelijk rechtstreeks aan een andere verwerkingsverantwoordelijke op mijn verzoek;",
                "bevestig welke gegevens wel en niet zijn opgenomen.",
            ],
        ),
        "legal_refs": "Art. 20, 12 AVG",
    },
    {
        "slug": "objection-request",
        "name": "Objection request",
        "right": "objection",
        "locale": "en",
        "subject": "GDPR objection — {{ case.reference }}",
        "body": body_en(
            "Article 21",
            "I object to the processing of my personal data for the purposes described above.",
            [
                "stop the processing without undue delay;",
                "if you rely on compelling legitimate grounds, explain them and provide the evidence;",
                "confirm that direct marketing has stopped, where applicable;",
                "inform recipients of the objection (Article 19 GDPR).",
            ],
        ),
        "legal_refs": "Art. 21, 19, 12 GDPR",
    },
    {
        "slug": "objection-request",
        "name": "Bezwaar tegen verwerking",
        "right": "objection",
        "locale": "nl",
        "subject": "AVG-bezwaar — {{ case.reference }}",
        "body": body_nl(
            "artikel 21",
            "Ik maak bezwaar tegen de verwerking van mijn persoonsgegevens voor de hierboven beschreven doeleinden.",
            [
                "stop de verwerking zonder onnodige vertraging;",
                "als u zich beroept op dwingende gerechtvaardigde gronden, leg deze dan uit en onderbouw ze;",
                "bevestig dat direct marketing is gestopt, indien van toepassing;",
                "informeer ontvangers over het bezwaar (artikel 19 AVG).",
            ],
        ),
        "legal_refs": "Art. 21, 19, 12 AVG",
    },
    {
        "slug": "consent-withdrawal",
        "name": "Consent withdrawal",
        "right": "consent_withdrawal",
        "locale": "en",
        "subject": "Withdrawal of consent — {{ case.reference }}",
        "body": body_en(
            "Article 7(3)",
            "I withdraw my consent for the processing described above.",
            [
                "confirm the withdrawal and stop the processing based on consent;",
                "explain the consequences of the withdrawal;",
                "confirm that the withdrawal does not affect the lawfulness of processing before this request.",
            ],
        ),
        "legal_refs": "Art. 7(3), 12 GDPR",
    },
    {
        "slug": "consent-withdrawal",
        "name": "Intrekking van toestemming",
        "right": "consent_withdrawal",
        "locale": "nl",
        "subject": "Intrekking van toestemming — {{ case.reference }}",
        "body": body_nl(
            "artikel 7, lid 3",
            "Ik trek mijn toestemming voor de hierboven beschreven verwerking in.",
            [
                "bevestig de intrekking en stop de verwerking die op toestemming is gebaseerd;",
                "leg de gevolgen van de intrekking uit;",
                "bevestig dat de intrekking geen afbreuk doet aan de rechtmatigheid van de verwerking vóór dit verzoek.",
            ],
        ),
        "legal_refs": "Art. 7, lid 3, en art. 12 AVG",
    },
    {
        "slug": "automated-decision-request",
        "name": "Automated decision explanation",
        "right": "automated_decision",
        "locale": "en",
        "subject": "Automated decision-making request — {{ case.reference }}",
        "body": body_en(
            "Article 22",
            "I request meaningful information about the automated decision-making described above.",
            [
                "explain the logic involved in the decision;",
                "explain the significance and envisaged consequences for me;",
                "confirm whether a human reviews the decision;",
                "arrange human intervention and let me express my point of view;",
                "confirm how I can contest the decision.",
            ],
        ),
        "legal_refs": "Art. 22, 13-15, 12 GDPR",
    },
    {
        "slug": "automated-decision-request",
        "name": "Uitleg geautomatiseerde besluitvorming",
        "right": "automated_decision",
        "locale": "nl",
        "subject": "Verzoek geautomatiseerde besluitvorming — {{ case.reference }}",
        "body": body_nl(
            "artikel 22",
            "Ik verzoek om zinvolle informatie over de hierboven beschreven geautomatiseerde besluitvorming.",
            [
                "leg de logica achter de beslissing uit;",
                "leg de betekenis en de voorziene gevolgen voor mij uit;",
                "bevestig of een mens de beslissing beoordeelt;",
                "zorg voor menselijke tussenkomst en stel mij in staat mijn standpunt kenbaar te maken;",
                "bevestig hoe ik de beslissing kan aanvechten.",
            ],
        ),
        "legal_refs": "Art. 22, 13-15, 12 AVG",
    },
    {
        "slug": "source-recipients-request",
        "name": "Source and recipients request",
        "right": "source",
        "locale": "en",
        "subject": "Source and recipients of my data — {{ case.reference }}",
        "body": body_en(
            "Articles 14 and 15",
            "Please tell me where my personal data came from and to whom it has been disclosed.",
            [
                "identify the source of the data, including public or commercial sources;",
                "identify the recipients or categories of recipients;",
                "explain any transfer outside the EEA and the safeguards used;",
                "state the retention period or criteria.",
            ],
        ),
        "legal_refs": "Art. 14, 15, 12 GDPR",
    },
    {
        "slug": "source-recipients-request",
        "name": "Bron en ontvangers van gegevens",
        "right": "source",
        "locale": "nl",
        "subject": "Bron en ontvangers van mijn gegevens — {{ case.reference }}",
        "body": body_nl(
            "de artikelen 14 en 15",
            "Ik verzoek u mij te vertellen waar mijn persoonsgegevens vandaan komen en aan wie ze zijn verstrekt.",
            [
                "noem de bron van de gegevens, inclusief publieke of commerciële bronnen;",
                "noem de ontvangers of categorieën van ontvangers;",
                "leg uit of gegevens buiten de EER zijn verstrekt en welke waarborgen daarbij gelden;",
                "noem de bewaartermijn of de criteria daarvoor.",
            ],
        ),
        "legal_refs": "Art. 14, 15, 12 AVG",
    },
    {
        "slug": "evidence-request",
        "name": "Evidence of lawful basis or deletion",
        "right": "evidence",
        "locale": "en",
        "subject": "Evidence request — {{ case.reference }}",
        "body": body_en(
            "the accountability principle in Article 5(2) and Article 7(1)",
            "Please provide evidence of the lawful basis for processing my personal data and, where applicable, of its deletion.",
            [
                "identify the lawful basis for each processing purpose;",
                "provide the consent record, if processing relies on consent;",
                "confirm the deletion and provide evidence, if you have deleted data;",
                "explain the retention period and the recipients of the data.",
            ],
        ),
        "legal_refs": "Art. 5(2), 7(1), 17, 12 GDPR",
    },
    {
        "slug": "evidence-request",
        "name": "Bewijs van grondslag of wissing",
        "right": "evidence",
        "locale": "nl",
        "subject": "Verzoek om bewijs — {{ case.reference }}",
        "body": body_nl(
            "het beginsel van verantwoordingsplicht in artikel 5, lid 2, en artikel 7, lid 1",
            "Ik verzoek u bewijs te leveren van de grondslag voor de verwerking van mijn persoonsgegevens en, indien van toepassing, van de wissing daarvan.",
            [
                "noem de grondslag voor elk verwerkingsdoel;",
                "verstrek het toestemmingsbewijs als de verwerking op toestemming is gebaseerd;",
                "bevestig de wissing en lever bewijs als u gegevens hebt verwijderd;",
                "leg de bewaartermijn en de ontvangers van de gegevens uit.",
            ],
        ),
        "legal_refs": "Art. 5, lid 2, 7, lid 1, 17 en 12 AVG",
    },
]
