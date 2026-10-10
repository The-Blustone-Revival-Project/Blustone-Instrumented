# Source after the preserved Episode+fishing+M008 profile; restart separately.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$veteranRoot=Split-Path $PSScriptRoot -Parent
$veteranAssets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $veteranAssets){$veteranAssets=Join-Path $veteranRoot 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$veteranPack=Join-Path $veteranAssets 'UI_SHOP.jet'
if(-not(Test-Path -LiteralPath $veteranPack -PathType Leaf)){throw 'Original UI_SHOP package missing'}
$veteranHash=(Get-FileHash -LiteralPath $veteranPack -Algorithm SHA256).Hash.ToLowerInvariant()
if($veteranHash -ne '89f3cc6750f01b3ca149ceece7c0798d963569bd8b6bb504c0c6be2b61162a09'){throw 'Original UI_SHOP package hash changed'}
if($InspectOnly){[pscustomobject]@{package='UI_SHOP.jet';bytes=(Get-Item $veteranPack).Length;sha256=$veteranHash};return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore the explicit established folded asset selection first'}
if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains 'M008.jet'){throw 'Restore the Story04 M008 profile before the Veteran icon profile'}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $veteranAssets).Path
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+'UI_SHOP.jet')|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634669'
$env:BLUSTONE_RESLIST_STAMP='1634669'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634669'
Write-Output 'Original UI_SHOP/ICON_VE profile prepared, stamp1634669; restart separately.'
