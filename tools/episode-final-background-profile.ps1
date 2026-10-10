# E01 Story07 late BG000_1; source after the Bear resource overlay.
# No restart/install/state mutation. Original DIAL_BG2 pack, no aliases.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$finalRoot=Split-Path $PSScriptRoot -Parent
$finalAssets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $finalAssets){$finalAssets=Join-Path $finalRoot 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$finalPack=Join-Path $finalAssets 'DIAL_BG2.jet'
if(-not(Test-Path -LiteralPath $finalPack -PathType Leaf)){throw 'Original DIAL_BG2 pack missing'}
$finalHash=(Get-FileHash -LiteralPath $finalPack -Algorithm SHA256).Hash.ToLowerInvariant()
if($finalHash -ne '3a432787750763d8becb9bd598419a352f06a01da2b5d40bd5dad3190ae001b7'){throw 'Original DIAL_BG2 hash changed'}
if($InspectOnly){[pscustomobject]@{Name='DIAL_BG2.jet';Bytes=(Get-Item -LiteralPath $finalPack).Length;SHA256=$finalHash};return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore the explicit existing resource selection first'}
foreach($finalRequired in @('M008.jet','UI_SHOP.jet','C036.jet','CUT_E0101.jet')){
  if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains $finalRequired){throw "Restore the previous original overlays: $finalRequired"}
}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $finalAssets).Path
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+'DIAL_BG2.jet')|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634671'
$env:BLUSTONE_RESLIST_STAMP='1634671'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634671'
Write-Output 'Original Story07 BG000_1 profile prepared, stamp1634671; restart separately. Native rendering pending.'
