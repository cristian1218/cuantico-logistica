.PHONY: setup test lint check seed dev dev-backend dev-frontend build

NODE_PATH ?= $(HOME)/.nvm/versions/node/v18.20.4/bin

setup:
	cd backend && uv sync
	export PATH="$(NODE_PATH):$$PATH" && cd frontend && npm install

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests

build: lint test
	export PATH="$(NODE_PATH):$$PATH" && cd frontend && npm run build

check: build

seed:
	cd backend && uv run python -m app.seed

dev-backend: seed
	cd backend && uv run uvicorn app.main:create_app --factory --reload --port 8000

dev-frontend:
	export PATH="$(NODE_PATH):$$PATH" && cd frontend && npm run dev

dev:
	@echo "Para iniciar el entorno completo:"
	@echo "  1) En una terminal: make dev-backend"
	@echo "  2) En otra terminal: make dev-frontend"
