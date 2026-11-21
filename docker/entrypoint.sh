#!/bin/sh
set -eu

DATA_DIR="${DATA_DIR:-/data}"
export DATA_DIR

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR/db" "$DATA_DIR/media" "$DATA_DIR/backups"
    chown -R app:app "$DATA_DIR"
    exec gosu app "$0" "$@"
fi

python manage.py migrate --noinput
python manage.py ensure_admin
python manage.py seed_templates

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
