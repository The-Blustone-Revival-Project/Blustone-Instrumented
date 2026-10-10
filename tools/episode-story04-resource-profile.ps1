# Source after the preserved Episode+fishing profile; does not restart or install.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$storyRoot=Split-Path $PSScriptRoot -Parent
$storyAssets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $storyAssets){$storyAssets=Join-Path $storyRoot 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$storyPack=Join-Path $storyAssets 'M008.jet'
if(-not(Test-Path -LiteralPath $storyPack -PathType Leaf)){throw 'Original M008 package missing'}
$storyHash=(Get-FileHash -LiteralPath $storyPack -Algorithm SHA256).Hash.ToLowerInvariant()
if($storyHash -ne '04b37480c31248de3a2a23f09901961923441a9ba7524abae037a0eb805074f5'){throw 'Original M008 package hash changed'}
if($InspectOnly){[pscustomobject]@{package='M008.jet';bytes=(Get-Item $storyPack).Length;sha256=$storyHash};return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB){throw 'Story04 requires the explicit existing asset selection'}
if(-not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore the established folded asset selection first'}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $storyAssets).Path
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+'M008.jet')|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
# M008 contains original M022 sprites/animations; never invent an M022 alias.
$env:BLUSTONE_RESOURCE_VERSION='1634668'
$env:BLUSTONE_RESLIST_STAMP='1634668'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634668'
Write-Output 'Story04 original M008/M022 resource profile prepared, stamp1634668; restart separately.'
