#!/usr/bin/env bash
# ==============================================================================
# Cuántico Logística — Script de Inicio Rápido (1 solo clic / comando)
# ==============================================================================

set -e

# Detectar Node 18+ si está en NVM
if [ -d "$HOME/.nvm/versions/node/v18.20.4/bin" ]; then
  export PATH="$HOME/.nvm/versions/node/v18.20.4/bin:$PATH"
fi

# 1. Copiar archivo de entorno si no existe
if [ ! -f .env ]; then
  echo "[1/3] Creando archivo .env desde .env.example..."
  cp .env.example .env
fi
if [ ! -f backend/.env ]; then
  cp .env.example backend/.env
fi

# 2. Inicializar la base de datos con los fixtures del sistema (idempotente)
echo "[2/3] Inicializando base de datos SQLite con datos iniciales..."
if command -v uv >/dev/null 2>&1; then
  (cd backend && uv run python -m app.seed >/dev/null 2>&1)
elif [ -f backend/.venv/bin/python ]; then
  (cd backend && .venv/bin/python -m app.seed >/dev/null 2>&1)
fi

# 3. Lanzar servicios concurrentemente
echo "[3/3] Levantando Backend y Frontend..."
echo ""
echo "======================================================================"
echo "  SISTEMA LISTO Y EN EJECUCION"
echo "======================================================================"
echo "  Frontend (App React):       http://localhost:5173"
echo "  Backend (FastAPI):          http://localhost:8000"
echo "  Swagger UI Interactivo:     http://localhost:8000/docs"
echo "======================================================================"
echo "  Presiona Ctrl + C en cualquier momento para detener los servicios."
echo "======================================================================"
echo ""

# Capturar señal de terminación para matar ambos subprocesos al presionar Ctrl+C
trap 'echo ""; echo "Deteniendo servidores..."; kill 0' SIGINT SIGTERM EXIT

if command -v uv >/dev/null 2>&1; then
  (cd backend && uv run uvicorn app.main:create_app --factory --port 8000 2>&1 | sed 's/^/[Backend] /') &
else
  (cd backend && .venv/bin/uvicorn app.main:create_app --factory --port 8000 2>&1 | sed 's/^/[Backend] /') &
fi

(cd frontend && npm run dev 2>&1 | sed 's/^/[Frontend] /') &

wait
