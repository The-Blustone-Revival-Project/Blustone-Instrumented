# Upload BLUSTONE-Instrumented.apk to a GitHub release, with retries.
#
# The APK is ~1.09 GB. A single `gh release upload` attempt can die with
# "HTTP 408: Upload body timed out due to inactivity" on a slow or interrupted
# link, and GitHub refuses a second asset with the same name. So this script
# retries the upload until the remote asset is byte-for-byte the expected size.
#
# Usage:
#   publish-apk.ps1 -Tag 2.8.0.1+3 [-ApkPath <path>] [-MaxAttempts 40]

param(
    [Parameter(Mandatory=$true)][string]$Tag,
    [string]$Repo = 'The-Blustone-Revival-Project/Blustone-Instrumented',
    [string]$ApkName = 'BLUSTONE-Instrumented.apk',
    [string]$ApkPath = '',
    [int]$MaxAttempts = 40,
    [int]$SleepSeconds = 20
)

$ErrorActionPreference = 'Continue'
if (-not $ApkPath) { $ApkPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'local/build/instrumented-apk/BLUSTONE-Instrumented.apk' }
$log = Join-Path $PSScriptRoot 'publish-apk.log'

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message
    Write-Output $line
    Add-Content -Path $log -Value $line
}

# Size of the already-uploaded asset, or $null when it is absent.
#
# Parse the JSON here in PowerShell instead of with a --jq filter. The first
# version of this script built the jq expression with escaped double quotes
# inside a PowerShell string, gh returned nothing, and the script misreported
# "upload did not complete" for an asset that had in fact uploaded fine - then
# retried 40 times against a file that was already correct.
function Get-RemoteAssetSize {
    $json = gh release view $Tag -R $Repo --json assets 2>$null
    if (-not $json) { return $null }
    $assets = ($json | ConvertFrom-Json).assets
    if (-not $assets) { return $null }
    $match = $assets | Where-Object { $_.name -eq $ApkName } | Select-Object -First 1
    if (-not $match) { return $null }
    return [int64]$match.size
}

if (-not (Test-Path $ApkPath)) { throw "APK not found: $ApkPath" }
if ($Tag -notmatch '^2\.8\.0\.1\+[1-9]\d*$') { throw 'Expected instrumented 2.8.0.1+N tag' }
$releasePolicy = gh release view $Tag -R $Repo --json isDraft,isPrerelease | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $releasePolicy.isDraft -or $releasePolicy.isPrerelease) { throw 'Upload helper requires an existing regular published release; use tools/release.py for new builds' }
$size = (Get-Item $ApkPath).Length
Write-Log "target release $Tag  asset $ApkName  $([math]::Round($size / 1MB, 1)) MB"

for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    # Accept an already-correct asset BEFORE doing anything destructive. A
    # completed upload must never be deleted because a check misread it.
    $existing = Get-RemoteAssetSize
    if ($existing -eq $size) {
        Write-Log "SUCCESS: $ApkName already present with the expected $existing bytes"
        exit 0
    }
    if ($null -ne $existing) {
        Write-Log "attempt ${attempt}: found $ApkName with $existing bytes (expected $size); replacing it"
        gh release delete-asset $Tag $ApkName -R $Repo --yes 2>&1 | ForEach-Object { Write-Log "  $_" }
    }

    Write-Log "attempt ${attempt}: uploading"
    gh release upload $Tag -R $Repo "$ApkPath#$ApkName" 2>&1 | ForEach-Object { Write-Log "  $_" }

    $uploaded = Get-RemoteAssetSize
    if ($uploaded -eq $size) {
        Write-Log "SUCCESS: $ApkName uploaded ($uploaded bytes)"
        exit 0
    }
    Write-Log "attempt ${attempt}: upload did not complete (got '$uploaded', want $size); retrying in ${SleepSeconds}s"
    Start-Sleep -Seconds $SleepSeconds
}

Write-Log "FAILED after $MaxAttempts attempts"
exit 1
