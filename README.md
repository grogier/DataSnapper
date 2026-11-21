# DataSnapper

A self-hosted web portal for keeping a privacy-rights case file and automating
the letters you send to companies under the GDPR.

DataSnapper is built for one person (the data subject) who wants to exercise
access, correction, deletion and related rights without handing their case file
to a third-party service. Everything stays in a local SQLite database and a
local media folder. There is no telemetry and no external API call.

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
cp .env.example .env
# Edit .env: set ALLOWED_HOSTS and a long ADMIN_PASSWORD.
# Leave SECRET_KEY and FIELD_ENCRYPTION_KEY empty to generate them on first start.

docker compose up -d --build
```

Open <http://localhost:8080> and sign in with the `ADMIN_USERNAME` and
`ADMIN_PASSWORD` from `.env`. On the first start the container runs migrations,
creates the admin user, seeds the 20 letter templates, and then starts Gunicorn.

The compose file bind-mounts `./data` to `/data` inside the container, so the
database, media and backups survive container rebuilds. Keep that directory on
an encrypted disk if possible.

Useful commands:

```bash
docker compose logs -f app
docker compose down
docker compose exec app python manage.py backup
docker compose exec app python manage.py verify_audit
```

For HTTPS, put the app behind a reverse proxy. `docker/Caddyfile.example` is a
minimal Caddy configuration; then set `CSRF_TRUSTED_ORIGINS` and the secure
cookie flags in `.env`.

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

Configuration is environment driven. Copy `.env.example` to `.env` for local
use or Docker.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEBUG` | `1` locally, `0` in `.env.example` | Debug mode. Keep `0` in production. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` when not debugging | Comma-separated hostnames. |
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

## The workflow

1. **Settings** — enter your name, email and postal address. Letters use these.
2. **Companies** — add the organisation, its privacy email or DPO, and the
   accounts or services you believe it holds.
3. **New case** — choose the right and describe the scope (accounts, email
   addresses, time period). This is what makes a request precise.
4. **Compose letter** — pick an English or Dutch template, preview, adjust the
   scope or add a paragraph, and save it as a draft.
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
core/              dashboard, settings, search, calendar, backups, shared models
companies/         organisations, contacts, data inventory
cases/             case model, rights, deadlines, transitions, checklists
correspondence/    templates, messages, attachments, PDF/EML export, evidence vault
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

## License

Add the license you intend to use before distributing this project. No license
file is included yet.
