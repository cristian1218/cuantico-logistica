.PHONY: setup test lint check seed dev dev-backend dev-frontend run build

NODE_PATH ?= $(shell if [ -d "$$HOME/.nvm/versions/node/v18.20.4/bin" ]; then echo "$$HOME/.nvm/versions/node/v18.20.4/bin"; fi)
PATH := $(if $(NODE_PATH),$(NODE_PATH):$(PATH),$(PATH))

setup:
	@test -f .env || cp .env.example .env
	@test -f backend/.env || cp .env.example backend/.env
	@if command -v uv >/dev/null 2>&1; then \
		cd backend && uv sync; \
	elif command -v python3 >/dev/null 2>&1; then \
		echo "Instalando uv para gestión rápida de Python..."; \
		python3 -m pip install uv && cd backend && uv sync || (cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"); \
	fi
	cd frontend && npm install
	@echo ""
	@echo "===================================================================="
	@echo "  ✅ Setup completado con éxito."
	@echo "  👉 Para iniciar todo con 1 comando: make run (o ./run.sh)"
	@echo "  👉 Para correr todos los tests:     make test"
	@echo "===================================================================="

seed:
	@test -f .env || cp .env.example .env
	@test -f backend/.env || cp .env.example backend/.env
	cd backend && (uv run python -m app.seed || .venv/bin/python -m app.seed)

test:
	cd backend && (uv run pytest -q || .venv/bin/pytest -q)

lint:
	cd backend && (uv run ruff check . && uv run ruff format --check . && uv run mypy app tests || (.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app tests))

build: lint test
	cd frontend && npm run build

check: build

run:
	@./run.sh

dev: run

dev-backend: seed
	cd backend && (uv run uvicorn app.main:create_app --factory --reload --port 8000 || .venv/bin/uvicorn app.main:create_app --factory --reload --port 8000)

dev-frontend:
	cd frontend && npm run dev
