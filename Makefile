.PHONY: install dev test lint format typecheck check \
        up down logs migrate migration rollback shell

install:
	pip install -r requirements/dev.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app

check:
	ruff check .
	ruff format --check .
	mypy app
	pytest

migrate:
	alembic upgrade head

migration:
	@test -n "$(message)" || (echo "Usage: make migration message='description'"; exit 1)
	alembic revision --autogenerate -m "$(message)"

rollback:
	alembic downgrade -1

shell:
	docker compose exec api /bin/sh