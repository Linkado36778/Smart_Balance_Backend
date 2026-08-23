#!/usr/bin/env sh
set -eu

INPUT="${1:-backups/smart-balance.sql}"

if [ ! -f "$INPUT" ]; then
    echo "Backup file not found: $INPUT" >&2
    exit 1
fi

docker compose up -d db
docker compose exec -T db psql -U postgres -d Smart-Balance < "$INPUT"

echo "Backup restored from $INPUT"
