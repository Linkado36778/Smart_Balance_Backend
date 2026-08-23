param(
    [string]$Output = "backups/smart-balance.sql",
    [string]$Database = "Smart-Balance",
    [string]$User = "postgres",
    [string]$HostName = "host.docker.internal",
    [int]$Port = 5432,
    [string]$ClientImage = "postgres:18-alpine"
)

$ErrorActionPreference = "Stop"

$backupDir = Split-Path -Parent $Output
if ($backupDir) {
    New-Item -ItemType Directory -Force $backupDir | Out-Null
}

$password = Read-Host "Postgres password for user '$User'" -AsSecureString
$plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
)

$tempOutput = "$Output.tmp"
if (Test-Path $tempOutput) {
    Remove-Item $tempOutput
}

try {
    docker run --rm `
        -e PGPASSWORD="$plainPassword" `
        $ClientImage `
        pg_dump `
        -h $HostName `
        -p $Port `
        -U $User `
        -d $Database `
        --clean `
        --if-exists > $tempOutput

    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed."
    }

    if (-not (Test-Path $tempOutput) -or (Get-Item $tempOutput).Length -eq 0) {
        throw "Backup failed or generated an empty file."
    }

    Move-Item -Force $tempOutput $Output
    Write-Host "Backup created at $Output"
}
finally {
    if (Test-Path $tempOutput) {
        Remove-Item $tempOutput
    }
}
