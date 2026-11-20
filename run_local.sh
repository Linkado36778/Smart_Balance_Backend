#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Inicia a API Smart Balance em modo desenvolvimento local.
#
#   ./run_local.sh
#
# Requisitos:
#   - .env na raiz do projeto (copie de .env.example e ajuste)
#   - .venv na raiz do projeto (veja o README.md)
#   - PostgreSQL local no ar: docker compose -f compose.dev.yml up -d
#
# A API fica em http://localhost:8000 (Swagger em /docs).
# Encerre com Ctrl+C.
# ----------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "ERRO: arquivo .env nao encontrado." >&2
    echo "Crie com: cp .env.example .env  (e ajuste as credenciais)" >&2
    exit 1
fi

# Exporta as variaveis do .env para o processo da API.
# Necessario para HF_HOME, SIGLIP_MODEL_NAME, TORCH_NUM_THREADS etc.
set -a
# shellcheck disable=SC1091
. ./.env
set +a

PYTHON_BIN=".venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    echo "ERRO: virtualenv .venv nao encontrado." >&2
    echo "Crie com: uv venv --python 3.13 .venv && UV_TORCH_BACKEND=cpu uv pip install -r requirements.txt" >&2
    echo "Ou com venv padrao: python3.13 -m venv .venv" >&2
    exit 1
fi

HOST="${APP_HOST:-0.0.0.0}"
PORT="${APP_PORT:-8000}"

# Aviso (nao fatal) se o PostgreSQL nao estiver acessivel.
if ! "$PYTHON_BIN" - "$POSTGRES_HOST" "$POSTGRES_PORT" <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=2):
        sys.exit(0)
except OSError:
    sys.exit(1)
PY
then
    echo "AVISO: PostgreSQL em ${POSTGRES_HOST}:${POSTGRES_PORT} nao respondeu." >&2
    echo "Suba o banco local com: docker compose -f compose.dev.yml up -d" >&2
fi

echo "APP_ENV=${APP_ENV:-development}"
echo "Python: $("$PYTHON_BIN" --version 2>&1)"
echo "API:      http://localhost:${PORT}"
echo "Swagger:  http://localhost:${PORT}/docs"
echo "Encerre com Ctrl+C."

exec "$PYTHON_BIN" -m uvicorn main:app --host "$HOST" --port "$PORT" --reload
