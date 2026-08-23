#!/usr/bin/env sh
set -eu

OUTPUT="${1:-backups/smart-balance.sql}"
BACKUP_DIR="$(dirname "$OUTPUT")"

mkdir -p "$BACKUP_DIR"

TEMP_OUTPUT="${OUTPUT}.tmp"
rm -f "$TEMP_OUTPUT"

docker compose up -d db

echo "Waiting for database to be ready..."
attempt=1
while ! docker compose exec -T db pg_isready -U postgres -d Smart-Balance >/dev/null 2>&1; do
    if [ "$attempt" -ge 30 ]; then
        echo "Database did not become ready in time." >&2
        exit 1
    fi

    attempt=$((attempt + 1))
    sleep 2
done

docker compose exec -T db pg_dump -U postgres -d Smart-Balance --clean --if-exists --file=/tmp/smart-balance.sql
docker compose cp db:/tmp/smart-balance.sql "$TEMP_OUTPUT"

if [ ! -s "$TEMP_OUTPUT" ]; then
    rm -f "$TEMP_OUTPUT"
    echo "Backup failed or generated an empty file." >&2
    exit 1
fi

mv "$TEMP_OUTPUT" "$OUTPUT"

echo "Backup created at $OUTPUT"
