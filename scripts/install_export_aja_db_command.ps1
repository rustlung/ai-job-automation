[CmdletBinding()]
param(
    [string]$BinDirectory = (Join-Path $HOME "bin")
)

$ErrorActionPreference = "Stop"

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ExporterScript = Join-Path $RepositoryRoot "scripts\export_aja_db.ps1"
if (-not (Test-Path -LiteralPath $ExporterScript -PathType Leaf)) {
    throw "Exporter script was not found: $ExporterScript"
}

New-Item -ItemType Directory -Path $BinDirectory -Force | Out-Null
$LauncherPath = Join-Path $BinDirectory "export_aja_db.cmd"
$LauncherContent = "@echo off`r`npowershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$ExporterScript`" %*`r`n"
[System.IO.File]::WriteAllText($LauncherPath, $LauncherContent, [System.Text.UTF8Encoding]::new($false))

$CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathEntries = @($CurrentUserPath -split ";" | Where-Object { $_ })
if ($PathEntries -notcontains $BinDirectory) {
    $UpdatedUserPath = @($PathEntries + $BinDirectory) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $UpdatedUserPath, "User")
    $PathChanged = $true
} else {
    $PathChanged = $false
}

Write-Host "Global command installed: $LauncherPath"
if ($PathChanged) {
    Write-Host "Open a new PowerShell window before running: export_aja_db"
} else {
    Write-Host "Run from any new PowerShell window: export_aja_db"
}
