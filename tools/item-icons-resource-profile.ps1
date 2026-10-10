# Original UI_ITEM artwork for the source-backed capsule thumbnail display.
# Source after complete separate E05 selection. No install/restart/grants.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$itemIconsRoot=Split-Path $PSScriptRoot -Parent
$itemIconsAssets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $itemIconsAssets){$itemIconsAssets=Join-Path $itemIconsRoot 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$itemIconsFile=Join-Path $itemIconsAssets 'UI_ITEM.jet'
$itemIconsHash='4b4350559330947254764f795902b2f66ea48826290316b9eb2bd295bd446eda'
if(-not(Test-Path -LiteralPath $itemIconsFile -PathType Leaf) -or
 (Get-FileHash -LiteralPath $itemIconsFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $itemIconsHash){throw 'Original UI_ITEM missing or changed'}
foreach($itemIconsPackageRoot in @((Join-Path $itemIconsRoot 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique){
 $itemIconsBundled=Join-Path $itemIconsPackageRoot 'UI_ITEM.jet'
 if((Test-Path -LiteralPath $itemIconsBundled) -and
   (-not(Test-Path -LiteralPath $itemIconsBundled -PathType Leaf) -or
    (Get-FileHash -LiteralPath $itemIconsBundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $itemIconsHash)){throw 'Bundled UI_ITEM conflicts with original'}
}
if($InspectOnly){[pscustomobject]@{Name='UI_ITEM.jet';Bytes=(Get-Item -LiteralPath $itemIconsFile).Length;SHA256=$itemIconsHash};return}
if($env:BLUSTONE_RESOURCE_ASSET_NAMES -ne ',' -or $env:BLUSTONE_RESOURCE_ASSET_GLOB){throw 'Restore complete separate resource selection first'}
foreach($itemIconsRequired in @('C012.jet','C030.jet','N001.jet','M016.jet','M018.jet','CUT_E0401.jet','UI_SHOP.jet','C017.jet','ST003.jet')){
 if(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',') -notcontains $itemIconsRequired){throw "Missing prior separate original: $itemIconsRequired"}
}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $itemIconsAssets).Path
$env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',')+'UI_ITEM.jet')|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634681'
$env:BLUSTONE_RESLIST_STAMP='1634681'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634681'
Write-Output 'Original UI_ITEM separate package selected, stamp1634681. Capsule full-size metadata is a local display choice; native validation pending.'
