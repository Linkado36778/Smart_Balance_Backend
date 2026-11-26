#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Rollback da API (executar NO SERVIDOR).
#
#   /opt/smart-balance/rollback.sh            -> volta para a tag anterior
#   /opt/smart-balance/rollback.sh <release>  -> volta para um release especifico
#
# Lista de imagens disponiveis: docker images sb-backend
# Banco de dados e volumes nao sao alterados.
# ----------------------------------------------------------------------------
set -euo pipefail

BASE=/opt/smart-balance
STATE="$BASE/state"

TARGET="${1:-$(cat "$STATE/previous_tag" 2>/dev/null || true)}"
CURRENT="$(cat "$STATE/current_tag" 2>/dev/null || true)"

[ -n "$TARGET" ] || { echo "ERRO: nenhuma tag anterior registrada." >&2; exit 1; }
docker image inspect "sb-backend:$TARGET" >/dev/null || { echo "ERRO: imagem sb-backend:$TARGET nao existe." >&2; exit 1; }

echo "Rollback: $CURRENT -> $TARGET"
IMAGE_TAG="$TARGET" docker compose -f "$BASE/compose.prod.yml" --env-file "$BASE/.env" up -d --no-deps api

for _ in $(seq 1 40); do
    if curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "$CURRENT" > "$STATE/previous_tag"
        echo "$TARGET" > "$STATE/current_tag"
        echo "$(date -u +%FT%TZ) rollback $TARGET" >> "$STATE/history"
        echo "OK: sb-backend:$TARGET no ar."
        exit 0
    fi
    sleep 3
done
echo "ERRO: /health nao respondeu apos rollback." >&2
exit 1
