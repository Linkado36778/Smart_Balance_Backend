#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Deploy de um release na VPS (executar NO SERVIDOR).
#
#   bash /opt/smart-balance/releases/<release>/deploy/deploy.sh <release>
#
# 1. Constroi a imagem sb-backend:<release> (a imagem anterior e mantida).
# 2. Atualiza o compose.prod.yml em /opt/smart-balance.
# 3. Sobe a API com a nova tag e espera o /health responder.
# 4. Se falhar, volta automaticamente para a tag anterior.
#
# Banco e volumes NAO sao tocados (somente o servico "api" e recriado).
# ----------------------------------------------------------------------------
set -euo pipefail

RELEASE="${1:?uso: deploy.sh <release>}"
BASE=/opt/smart-balance
SRC="$BASE/releases/$RELEASE"
STATE="$BASE/state"

cd "$BASE"
mkdir -p "$STATE"

[ -f "$BASE/.env" ] || { echo "ERRO: $BASE/.env nao existe." >&2; exit 1; }

PREVIOUS_TAG="$(cat "$STATE/current_tag" 2>/dev/null || true)"

echo "==> Build sb-backend:$RELEASE"
docker build -f "$SRC/deploy/Dockerfile" -t "sb-backend:$RELEASE" "$SRC"

install -m 644 "$SRC/deploy/compose.prod.yml" "$BASE/compose.prod.yml"
install -m 755 "$SRC/deploy/rollback.sh" "$BASE/rollback.sh"

compose() { IMAGE_TAG="$1" docker compose -f "$BASE/compose.prod.yml" --env-file "$BASE/.env" "${@:2}"; }

echo "==> Subindo banco (se necessario) e API $RELEASE"
compose "$RELEASE" up -d db
compose "$RELEASE" up -d --no-deps api

echo "==> Aguardando /health"
for _ in $(seq 1 40); do
    if curl -fsS --max-time 5 http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "$PREVIOUS_TAG" > "$STATE/previous_tag"
        echo "$RELEASE" > "$STATE/current_tag"
        echo "$(date -u +%FT%TZ) $RELEASE" >> "$STATE/history"
        echo "OK: sb-backend:$RELEASE no ar."
        exit 0
    fi
    sleep 3
done

echo "ERRO: /health nao respondeu. Ultimos logs:" >&2
docker logs --tail 80 sb-backend >&2 || true

if [ -n "$PREVIOUS_TAG" ]; then
    echo "==> Rollback automatico para $PREVIOUS_TAG" >&2
    compose "$PREVIOUS_TAG" up -d --no-deps api
fi
exit 1
