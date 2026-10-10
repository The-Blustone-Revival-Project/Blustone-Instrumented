# Optional original fishing CDN packages. No APK install, restart or client reset.
# Source after the separate Episode profile if both areas are being investigated.
param([switch]$InspectOnly)
$ErrorActionPreference = 'Stop'
$fishingRoot = Split-Path $PSScriptRoot -Parent
$fishingAssets = $env:BLUSTONE_RESOURCE_ASSET_DIR
if (-not $fishingAssets) {
    $fishingAssets = Join-Path $fishingRoot 'recovered-assets\phone-2026-09-18\extracted\split_PADResource\assets'
}
$fishingAssets = (Resolve-Path -LiteralPath $fishingAssets).Path
$fishingPacks = @('FISHING.jet', 'FISH_LIST.jet', 'MGM_FISH.jet', 'LEVELING.jet')
$fishingInventory = @($fishingPacks | ForEach-Object {
    $fishingFile = Join-Path $fishingAssets $_
    if (-not (Test-Path -LiteralPath $fishingFile -PathType Leaf)) { throw "Missing original fishing pack: $_" }
    $fishingSize = (Get-Item -LiteralPath $fishingFile).Length
    if ($fishingSize -lt 24) { throw "Invalid fishing pack size: $_" }
    [pscustomobject]@{ Name = $_; Bytes = $fishingSize; SHA256 = (Get-FileHash -LiteralPath $fishingFile -Algorithm SHA256).Hash.ToLowerInvariant() }
})
if ($InspectOnly) { $fishingInventory; return }
if ($env:BLUSTONE_RESOURCE_ASSET_GLOB) { throw 'Separate fishing packages require an empty resource asset glob.' }
$env:BLUSTONE_RESOURCE_ASSET_DIR = $fishingAssets
foreach ($selectionName in @('BLUSTONE_RESOURCE_ASSET_NAMES', 'BLUSTONE_RESOURCE_ASSET_NAMES_EXTRA')) {
    $selectionValue = [Environment]::GetEnvironmentVariable($selectionName)
    if ($selectionValue) {
        [Environment]::SetEnvironmentVariable($selectionName, (@($selectionValue -split ',' |
            ForEach-Object { $_.Trim() } | Where-Object { $_ -and $_ -notin $fishingPacks }) -join ','))
    }
}
$env:BLUSTONE_PACKAGE_NAMES_EXTRA = (@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',') + $fishingPacks) |
    ForEach-Object { $_.Trim() } | Where-Object { $_ } | Select-Object -Unique) -join ','
$env:BLUSTONE_RESOURCE_VERSION = '1634667'
$env:BLUSTONE_RESLIST_STAMP = '1634667'
$env:BLUSTONE_RESLIST_HEADER_STAMP = '1634667'
Write-Output 'Fishing resource profile prepared: four separate original JET packages, stamp1634667. Native fishing remains unverified; restart separately.'
