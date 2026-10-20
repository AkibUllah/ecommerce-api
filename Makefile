.PHONY: install dev migrate run seed test lint fmt release-expired compose-up compose-down

PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

migrate:
	$(PY) manage.py migrate

run:
	$(PY) manage.py runserver 0.0.0.0:8000

seed:
	$(PY) manage.py seed_demo

release-expired:
	$(PY) manage.py release_expired_reservations

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .

fmt:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down -v
