param(
    [string]$Input = "backups/smart-balance.sql"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Input)) {
    throw "Backup file not found: $Input"
}

docker compose up -d db
docker compose exec -T db psql -U postgres -d Smart-Balance < $Input

Write-Host "Backup restored from $Input"
