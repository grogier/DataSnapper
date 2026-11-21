# DataSnapper

A self-hosted web portal for keeping a privacy-rights case file and automating
the letters you send to companies under the GDPR.

DataSnapper is built for one person (the data subject) who wants to exercise
access, correction, deletion and related rights without handing their case file
to a third-party service. Everything stays in a local SQLite database and a
local media folder. There is no telemetry. The only outbound calls are optional
LLM requests that you explicitly enable and configure.

> **Legal disclaimer:** the built-in letters are practical starting points, not
> legal advice. They cite the GDPR only. Check the facts of your case, adapt the
> scope and wording, and consult a lawyer or your national supervisory authority
> if a controller refuses or the matter escalates.

## What it does

- **Case file per company and per right** with a reference such as
  `DSAR-2026-0001`, scope, priority, notes and a full timeline.
- **Ten request types** with a response checklist: access, rectification,
  erasure, restriction, portability, objection, consent withdrawal, automated
  decision-making, source/recipients, and evidence of lawful basis or deletion.
- **Deadline tracking** for the GDPR one-month period, plus the optional
  three-month total extension with a notice date.
- **Letter templates in English and Dutch**, versioned so a sent letter keeps
  the text it was sent with.
- **Optional AI assistance** with a local Ollama model or a cloud
  OpenAI-compatible/DeepSeek endpoint: describe the scope, draft a letter, or
  rewrite a draft. Off by default.
- **Manual-first sending:** preview, export PDF, download `.eml`, print, or copy
  the text into a web form, then mark the message sent. Marking it sent starts
  the deadline.
- **Correspondence log:** inbound replies, notes, tasks, documents and status
  changes all land on the case timeline.
- **Evidence vault** with hash records, and encryption at rest for identity
  documents.
- **Append-only audit log** with a SHA-256 hash chain and a verification command.
- **Dashboard, search, calendar and `.ics` export** for upcoming deadlines.
- **Single-user login**, local SQLite storage, Docker image, no Node build step.

SMTP and IMAP are intentionally not part of v1. You send with your own mail
client and record the result, which keeps credentials and mail content out of
the portal.

## Quick start with Docker

Requirements: Docker with Compose v2.

```bash
docker compose pull
docker compose up -d
```

This uses the prebuilt image from
`ghcr.io/grogier/datasnapper:latest`; nothing is compiled locally. It works
without any configuration file. The compose file passes local defaults
(`DEBUG=0`, `ADMIN_USERNAME=admin`, `ALLOWED_HOSTS` for localhost) and generates
the secret keys in `./data` on first start. If `ADMIN_PASSWORD` is not set, a
password is generated and printed once:

```bash
docker compose logs app | grep -A2 "Generated password"
```

To choose settings up front, either export variables or create a `.env`. A
`.env` file is optional and is read automatically when present:

```bash
ADMIN_PASSWORD='a-long-password' ALLOWED_HOSTS=localhost,192.168.1.20 \
  docker compose up -d

# or: cp .env.example .env  and edit it
```

Open <http://localhost:8080> and sign in with `ADMIN_USERNAME` (default
`admin`) and your `ADMIN_PASSWORD`. On the first start the container runs
migrations, creates the admin user, seeds the 20 letter templates, and then
starts Gunicorn.

The compose file bind-mounts `./data` to `/data` inside the container, so the
database, media and backups survive container upgrades. Keep that directory on
an encrypted disk if possible.

Useful commands:

```bash
docker compose logs -f app
docker compose down
docker compose exec app python manage.py backup
docker compose exec app python manage.py verify_audit

# update to the newest published image
docker compose pull && docker compose up -d
```

`latest` follows the default branch. To stay on a specific build, pin the tag
(branch name, git tag, or `sha-<commit>`) in `.env` or on the command line:

```bash
DATASNAPPER_TAG=main docker compose pull && docker compose up -d
```

For HTTPS, put the app behind a reverse proxy. `docker/Caddyfile.example` is a
minimal Caddy configuration; then set `CSRF_TRUSTED_ORIGINS` and the secure
cookie flags as environment variables or in `.env`.

## Local development

Requirements: Python 3.12+ and the WeasyPrint system libraries
(`libpango-1.0-0`, `libpangoft2-1.0-0`, `libcairo2`,
`libgdk-pixbuf-2.0-0`, `shared-mime-info`).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

export DATA_DIR="$PWD/data"
.venv/bin/python manage.py migrate
.venv/bin/python manage.py ensure_admin
.venv/bin/python manage.py seed_templates
.venv/bin/python manage.py runserver
```

Then open <http://127.0.0.1:8000>. If `ADMIN_PASSWORD` is not set,
`ensure_admin` prints a generated password once; change it after signing in.

Run the checks:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Configuration

Configuration is environment driven and has working defaults. A `.env` file is
optional; export variables, create `.env`, or pass them inline with Docker
Compose. See `.env.example` for the full list.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEBUG` | `1` locally, `0` in Docker | Debug mode. Keep `0` in production. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` locally, adds `datasnapper.local` in Docker | Comma-separated hostnames. |
| `CSRF_TRUSTED_ORIGINS` | empty | Required for HTTPS origins, e.g. `https://cases.example.com`. |
| `DATA_DIR` | `./data` locally, `/data` in Docker | Database, media, backups and generated keys. |
| `DATABASE_PATH` | `$DATA_DIR/db/datasnapper.sqlite3` | Override the SQLite file. |
| `MEDIA_ROOT` | `$DATA_DIR/media` | Uploaded documents. |
| `BACKUP_DIR` | `$DATA_DIR/backups` | Backup archives. |
| `SECRET_KEY` | generated into `$DATA_DIR/secret.key` | Django signing key. |
| `FIELD_ENCRYPTION_KEY` | generated into `$DATA_DIR/field.key` | Fernet key for identity documents and encrypted backups. |
| `ADMIN_USERNAME` | `admin` | First user, created only when no user exists. |
| `ADMIN_EMAIL` | empty | First user's email. |
| `ADMIN_PASSWORD` | generated and printed | First user's password. |
| `TIME_ZONE` | `Europe/Amsterdam` | Local dates and reminders. |
| `LANGUAGE_CODE` | `en` | UI language. Letter language is per template. |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS` | off | Enable when served over HTTPS. |
| `BACKUP_RETENTION` | `14` | Number of backup archives to keep. |
| `BACKUP_ENCRYPT` | `1` | Set `0` to write unencrypted archives. |
| `GUNICORN_WORKERS`, `GUNICORN_THREADS` | `2`, `4` | Gunicorn tuning. |
| `GUNICORN_TIMEOUT` | `180` | Worker timeout. Raise it if a local model is slow. |
| `LLM_ENABLED` | `0` | Enable AI assistance for drafting requests. |
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai` or `deepseek`. |
| `LLM_BASE_URL` | provider default | Endpoint override, e.g. `http://host.docker.internal:11434`. |
| `LLM_MODEL` | provider default | Model name, e.g. `llama3.1:8b` or `deepseek-flash`. |
| `LLM_TIMEOUT` | `120` | Seconds to wait for the model. |
| `LLM_MAX_OUTPUT_TOKENS` | `1500` | Output cap. |
| `LLM_REASONING` | `0` | Default for the reasoning/thinking toggle. |
| `LLM_SHARE_PERSONAL_DATA` | `0` | Send your name, address and contact details to the model. |
| `DEEPSEEK_API_KEY` | empty | DeepSeek key. Environment only, never stored in the database. |
| `OPENAI_API_KEY` | empty | OpenAI-compatible key. |
| `LLM_API_KEY` | empty | Generic fallback key, e.g. for OpenRouter. |

## AI assistance

AI assistance is optional and disabled by default. When enabled, the compose
page can describe the request (scope), draft a full letter, or rewrite an
existing draft. The generated text is always shown in an editable box first; it
is saved as a normal draft and still needs your review before sending.

### Local Ollama (default)

```bash
# Install Ollama, then pull a model:
ollama pull llama3.1:8b

# Local development: Settings -> AI assistance -> Enable.
# Default endpoint: http://localhost:11434
```

With Docker, use `LLM_BASE_URL=http://host.docker.internal:11434` for Ollama on
the host, or enable the commented `ollama` Compose profile and use
`http://ollama:11434`:

```bash
docker compose --profile llm up -d
docker compose exec ollama ollama pull llama3.1:8b
```

Dutch letters are usually better with a multilingual model such as
`qwen2.5:7b` or `mistral-nemo`, if your hardware can run it.

### DeepSeek (cloud)

```bash
LLM_ENABLED=1
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
DEEPSEEK_API_KEY=sk-...
```

DeepSeek is OpenAI-compatible. `deepseek-flash` is the fast, inexpensive model;
`deepseek-v4-pro` is stronger. The reasoning toggle maps to DeepSeek thinking
mode, which is slower and better for complex scope. Thinking is explicitly
disabled when the toggle is off. DeepSeek is a cloud service outside the EU, so
prompts leave your server; enable it only if that is acceptable for your case.

### Any OpenAI-compatible endpoint

Set `LLM_PROVIDER=openai`, the provider's base URL and model, and either
`OPENAI_API_KEY` or `LLM_API_KEY`. This covers OpenAI, OpenRouter, Groq, vLLM,
LM Studio and Ollama's `/v1` endpoint.

### Privacy

- **Placeholder mode is the default.** Your name, email and postal address are
  not included in the prompt. The model writes `{{ profile.full_name }}` and
  similar placeholders, which DataSnapper fills in locally.
- **Notes are sent as written.** The scope and case notes you typed are part of
  the prompt, so do not put identity numbers or other secrets in them.
- **Show prompt** displays the exact system and user text before anything is
  sent, including the endpoint it will go to.
- **Keys live in the environment only.** They are never stored in the database,
  rendered in the UI, or written to logs.
- **Audit without content.** The audit log records provider, model, token counts
  and a prompt hash — never the prompt or the generated letter.
- Enable `LLM_SHARE_PERSONAL_DATA=1` only if you want the model to see the real
  profile and company details for better context. The output still uses
  placeholders.

Use **Test connection** in Settings to check the endpoint and list available
models. If a request times out, raise `LLM_TIMEOUT` and `GUNICORN_TIMEOUT`.

## The workflow

1. **Settings** — enter your name, email and postal address. Letters use these.
2. **Companies** — add the organisation, its privacy email or DPO, and the
   accounts or services you believe it holds.
3. **New case** — choose the right and describe the scope (accounts, email
   addresses, time period). This is what makes a request precise.
4. **Compose letter** — pick an English or Dutch template, preview, adjust the
   scope or add a paragraph, and save it as a draft. If AI assistance is
   enabled, ask it to describe the scope or draft the letter, then edit the
   result before saving.
5. **Send it your way** — download the PDF, the `.eml`, print it, or copy the
   text into a web form. Then mark the message as sent. The case moves to
   *Sent* and the one-month deadline is calculated.
6. **Log what comes back** — record replies, upload the response and any data
   package, tick the response checklist, and move the case through
   acknowledged, identity check, in progress, fulfilled, refused or no
   response.
7. **Escalate or close** — if the controller misses the deadline or refuses,
   escalate the case. Close it when you are done.

The case timeline and the audit log record each step, so you have a dated trail
if you need to complain to a supervisory authority.

## Deadlines

- The due date is one calendar month after the sent date, clamped to the last
  day of the month (sending on 31 January makes the deadline 28 or 29 February).
- If the controller invokes the two-month extension, record the date of its
  notice on the case. The effective deadline becomes three months after sending.
- The dashboard, case list, calendar and `.ics` export all use the effective
  deadline. Overdue and due-soon states are colour coded.
- Reminder offsets are configurable in Settings (default `10,3,0` days) and
  feed the calendar and dashboard views.

## Documents and encryption

- Identity documents are encrypted at rest with Fernet using
  `FIELD_ENCRYPTION_KEY` (or `$DATA_DIR/field.key`). Downloads are decrypted on
  the fly and logged.
- Other documents (proof of sending, company responses, data exports) are
  stored as normal files in `$DATA_DIR/media`.
- Every attachment records its size, MIME type and SHA-256 hash.
- Maximum upload size is 25 MB.

## Backup and restore

Create an encrypted archive of the database, media and keys:

```bash
python manage.py backup
# or inside Docker:
docker compose exec app python manage.py backup
```

By default the archive is `$DATA_DIR/backups/datasnapper-backup-<timestamp>.tar.gz.enc`,
encrypted with the field key, and the last 14 archives are kept. Use
`--no-encrypt` to write a plain `.tar.gz`, and `BACKUP_RETENTION=0` to keep
everything.

Restore:

```bash
python manage.py decrypt_backup /data/backups/datasnapper-backup-....tar.gz.enc \
    --output /tmp/datasnapper-backup.tar.gz
tar -xzf /tmp/datasnapper-backup.tar.gz -C /data
python manage.py migrate
python manage.py verify_audit
```

**Keep `secret.key` and `field.key` somewhere safe outside the container**, for
example in a password manager. Without the field key, encrypted identity
documents and encrypted backups cannot be recovered. The backup archive includes
the keys for convenience, so treat every backup as sensitive as the original
data.

## Security notes

- Every page except the login screen and `/healthz` requires authentication.
- CSRF protection, clickjacking protection, MIME sniffing protection and a
  same-origin referrer policy are enabled.
- The audit log is append-only in the UI and admin, and each entry contains the
  hash of the previous entry. `python manage.py verify_audit` reports the first
  broken link.
- The portal is designed for a private network. If you expose it to the
  internet, terminate TLS at a reverse proxy, set the secure cookie flags and
  `SECURE_SSL_REDIRECT`, and keep the host patched.
- There is one user account by design. Create additional Django users only if
  you understand that they share the same case file.
- AI assistance is opt-in. When enabled, prompt text is sent to the endpoint you
  configured; DataSnapper adds no telemetry of its own. Use a local Ollama model
  if the case file must not leave your network.

## Maintenance commands

```bash
python manage.py ensure_admin        # create the first user if none exists
python manage.py seed_templates      # add missing EN/NL templates
python manage.py refresh_deadlines   # fill missing due dates
python manage.py purge_expired       # report old closed cases (add --yes to delete)
python manage.py backup              # encrypted backup
python manage.py decrypt_backup ...  # decrypt a backup
python manage.py verify_audit        # check the audit hash chain
```

`purge_expired` uses the retention period in Settings. `0` disables deletion,
which is the default.

## Project layout

```
config/            Django settings, URLs, WSGI/ASGI
core/              dashboard, settings, search, calendar, backups, shared models,
                   optional LLM client under core/llm/
companies/         organisations, contacts, data inventory
cases/             case model, rights, deadlines, transitions, checklists
correspondence/    templates, messages, attachments, PDF/EML export, evidence vault,
                   AI prompt building in assist.py
audit/             hash-chained audit log
templates/         HTML templates and the PDF letter layout
static/            hand-written CSS, small JS helpers, vendored HTMX
tests/             pytest suite
docker/            Dockerfile, entrypoint, Caddy example
```

The stack is Django 5.2, SQLite (WAL mode), HTMX, hand-written CSS and
WeasyPrint. There is no Node or asset build step, so the image builds offline
after the Python dependencies are fetched.

## Limitations and next steps

- No SMTP/IMAP integration in v1; sending is manual by design.
- One data-subject profile; the models allow more but the UI is single-profile.
- Letter templates cover the GDPR and are English/Dutch only.
- No public tokenized calendar feed; the `.ics` download requires login.
- National procedural rules, complaint templates and authority-specific
  escalation letters are not included.
- AI output can be wrong or invent a detail. It is a drafting aid, not legal
  advice; check facts and citations before sending.

## License

Add the license you intend to use before distributing this project. No license
file is included yet.
