#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Envia uma nova versao do backend para a VPS (executar NA MAQUINA LOCAL).
#
#   deploy/push_release.sh [ssh_destino]      (padrao: root@179.66.157.98)
#
# Copia somente os arquivos necessarios da API para
#   /opt/smart-balance/releases/<commit>-<timestamp>
# e em seguida executa o deploy.sh remoto com esse release.
# Nada e removido: releases anteriores continuam disponiveis para rollback.
# ----------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

DEST="${1:-root@179.66.157.98}"
BASE=/opt/smart-balance

# Chave SSH usada no deploy (padrao: ~/.ssh/id_buildroot). Para usar a
# configuracao normal do ssh: SB_SSH_KEY= deploy/push_release.sh
SB_SSH_KEY="${SB_SSH_KEY-$HOME/.ssh/id_buildroot}"
SSH_CMD=(ssh -o BatchMode=yes)
if [ -n "$SB_SSH_KEY" ]; then
    SSH_CMD+=(-o IdentitiesOnly=yes -i "$SB_SSH_KEY")
fi
ssh() { command "${SSH_CMD[@]}" "$@"; }

if [ -n "$(git status --porcelain -- main.py application shared SiglIp/test_01_Siglip.py images requirements.txt deploy)" ]; then
    echo "AVISO: ha alteracoes nao commitadas nos arquivos do release." >&2
fi

RELEASE="$(git rev-parse --short HEAD)-$(date -u +%Y%m%d%H%M%S)"
echo "Release: $RELEASE -> $DEST:$BASE/releases/$RELEASE"

ssh "$DEST" "mkdir -p $BASE/releases/$RELEASE"

rsync -az --delete -e "${SSH_CMD[*]}" \
    --exclude '__pycache__' --exclude '*.pyc' \
    --relative \
    main.py \
    requirements.txt \
    application \
    shared \
    SiglIp/test_01_Siglip.py \
    images \
    deploy/Dockerfile \
    deploy/compose.prod.yml \
    deploy/deploy.sh \
    deploy/rollback.sh \
    "$DEST:$BASE/releases/$RELEASE/"

ssh "$DEST" "bash $BASE/releases/$RELEASE/deploy/deploy.sh $RELEASE"
