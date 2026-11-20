param(
    [string]$Output = "backups/smart-balance.sql"
)

$ErrorActionPreference = "Stop"

$backupDir = Split-Path -Parent $Output
if ($backupDir) {
    New-Item -ItemType Directory -Force $backupDir | Out-Null
}

$tempOutput = "$Output.tmp"

if (Test-Path $tempOutput) {
    Remove-Item $tempOutput
}

docker compose up -d db

Write-Host "Waiting for database to be ready..."
for ($attempt = 1; $attempt -le 30; $attempt++) {
    docker compose exec -T db pg_isready -U postgres -d Smart-Balance | Out-Null
    if ($LASTEXITCODE -eq 0) {
        break
    }

    if ($attempt -eq 30) {
        throw "Database did not become ready in time."
    }

    Start-Sleep -Seconds 2
}

docker compose exec -T db pg_dump -U postgres -d Smart-Balance --clean --if-exists --file=/tmp/smart-balance.sql
docker compose cp db:/tmp/smart-balance.sql $tempOutput

if (-not (Test-Path $tempOutput) -or (Get-Item $tempOutput).Length -eq 0) {
    if (Test-Path $tempOutput) {
        Remove-Item $tempOutput
    }
    throw "Backup failed or generated an empty file."
}

Move-Item -Force $tempOutput $Output

Write-Host "Backup created at $Output"
