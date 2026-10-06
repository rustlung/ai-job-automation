[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RemoteHost = "server"
$RemoteProject = "~/services/ai-job-automation/orchestrator"
$RemoteSnapshotRelativePath = "data/app-dbeaver-export.db"
$RemoteSnapshotPath = "$RemoteProject/$RemoteSnapshotRelativePath"
$LocalDirectory = "C:\ai-job-automation_db_backup"
$LocalFile = Join-Path $LocalDirectory "ai-job-automation.db"
$LocalTemporaryFile = Join-Path $LocalDirectory "ai-job-automation.db.tmp"

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Stage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Stage failed (exit code $LASTEXITCODE)."
    }
}

function Remove-RemoteSnapshot {
    $cleanupCommand = "cd $RemoteProject && rm -f -- $RemoteSnapshotRelativePath"
    Invoke-NativeCommand -FilePath "ssh" -Arguments @($RemoteHost, $cleanupCommand) -Stage "Remote snapshot cleanup"
}

try {
    $remoteSnapshotCreated = $false
    New-Item -ItemType Directory -Path $LocalDirectory -Force | Out-Null
    Remove-Item -LiteralPath $LocalTemporaryFile -Force -ErrorAction SilentlyContinue

    $createCommand = "cd $RemoteProject && docker compose run --rm api python -m app.scripts.export_database_snapshot --output /app/data/app-dbeaver-export.db"
    Invoke-NativeCommand -FilePath "ssh" -Arguments @($RemoteHost, $createCommand) -Stage "Remote SQLite snapshot creation"
    $remoteSnapshotCreated = $true

    Invoke-NativeCommand -FilePath "scp" -Arguments @("${RemoteHost}:$RemoteSnapshotPath", $LocalTemporaryFile) -Stage "Snapshot download"
    Remove-RemoteSnapshot
    $remoteSnapshotCreated = $false

    if (Test-Path -LiteralPath $LocalFile) {
        [System.IO.File]::Replace($LocalTemporaryFile, $LocalFile, $null)
    } else {
        [System.IO.File]::Move($LocalTemporaryFile, $LocalFile)
    }

    Write-Host "Database snapshot exported successfully:"
    Write-Host $LocalFile
}
catch {
    $failureMessage = $_.Exception.Message
    Remove-Item -LiteralPath $LocalTemporaryFile -Force -ErrorAction SilentlyContinue
    if ($remoteSnapshotCreated) {
        try {
            Remove-RemoteSnapshot
        } catch {
            Write-Warning "Remote temporary snapshot cleanup failed."
        }
    }
    Write-Error "Database snapshot export failed: $failureMessage"
    exit 1
}
