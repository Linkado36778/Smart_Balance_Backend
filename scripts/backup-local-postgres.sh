#!/usr/bin/env sh
set -eu

OUTPUT="${1:-backups/smart-balance.sql}"
DATABASE="${POSTGRES_DB:-Smart-Balance}"
USER="${POSTGRES_USER:-postgres}"
HOST_NAME="${POSTGRES_HOST:-host.docker.internal}"
PORT="${POSTGRES_PORT:-5432}"
CLIENT_IMAGE="${POSTGRES_CLIENT_IMAGE:-postgres:18-alpine}"
BACKUP_DIR="$(dirname "$OUTPUT")"
TEMP_OUTPUT="${OUTPUT}.tmp"

mkdir -p "$BACKUP_DIR"
rm -f "$TEMP_OUTPUT"

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
    printf "Postgres password for user '%s': " "$USER" >&2
    stty -echo
    read -r POSTGRES_PASSWORD
    stty echo
    printf "\n" >&2
fi

docker run --rm \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    "$CLIENT_IMAGE" \
    pg_dump \
    -h "$HOST_NAME" \
    -p "$PORT" \
    -U "$USER" \
    -d "$DATABASE" \
    --clean \
    --if-exists > "$TEMP_OUTPUT"

if [ ! -s "$TEMP_OUTPUT" ]; then
    rm -f "$TEMP_OUTPUT"
    echo "Backup failed or generated an empty file." >&2
    exit 1
fi

mv "$TEMP_OUTPUT" "$OUTPUT"
echo "Backup created at $OUTPUT"
