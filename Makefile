.PHONY: install migrate run test lint seed backup docker-up docker-down

# Keep local commands on ./data even if .env was copied for Docker (DATA_DIR=/data).
DATA_DIR ?= $(CURDIR)/data
export DATA_DIR

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt

migrate:
	.venv/bin/python manage.py migrate
	.venv/bin/python manage.py seed_templates

run:
	.venv/bin/python manage.py runserver 0.0.0.0:8000

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

seed:
	.venv/bin/python manage.py seed_templates

backup:
	.venv/bin/python manage.py backup

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
