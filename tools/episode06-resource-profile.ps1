# Complete original E06 Bibi combat family and Dino portrait. Source after
# complete separate E05 + UI_ITEM profile; no install/restart/grants/stat edits.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$episode06Root=Split-Path $PSScriptRoot -Parent
$episode06Assets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $episode06Assets){$episode06Assets=Join-Path $episode06Root 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$episode06Hashes=[ordered]@{
 'C040.jet'='34c15d85a1ada674be94cb9a7a29906765f3029da6191512f2a5ee951ebd7df4'
 'C040_EFT.jet'='7fcfc6a40dd56b8ddd8301838d0fce989cff1747b705c5937824a438ea61425e'
 'C040_Q.jet'='029b991a93eb6f3d9d7aea668bdf75006218957de09211378a4013306126718b'
 'C040_SND.jet'='707e9a8e20b66432f48cd6ce6a4bd06265e9f88cc2dfeee7b40db52fa1c25de0'
 'C054.jet'='540341367e541025f3a8bdf8679aade97b13f9a5c3d65cd01f96afa639536ab8'
}
$episode06Inventory=@(foreach($episode06Entry in $episode06Hashes.GetEnumerator()){
 $episode06File=Join-Path $episode06Assets $episode06Entry.Key
 if(-not(Test-Path -LiteralPath $episode06File -PathType Leaf) -or
   (Get-FileHash -LiteralPath $episode06File -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode06Entry.Value){throw "Original E06 pack missing/changed: $($episode06Entry.Key)"}
 foreach($episode06PackageRoot in @((Join-Path $episode06Root 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique){
  $episode06Bundled=Join-Path $episode06PackageRoot $episode06Entry.Key
  if((Test-Path -LiteralPath $episode06Bundled) -and
    (-not(Test-Path -LiteralPath $episode06Bundled -PathType Leaf) -or
     (Get-FileHash -LiteralPath $episode06Bundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode06Entry.Value)){throw "Bundled E06 conflict: $($episode06Entry.Key)"}
 }
 [pscustomobject]@{Name=$episode06Entry.Key;Bytes=(Get-Item -LiteralPath $episode06File).Length;SHA256=$episode06Entry.Value}
})
if($InspectOnly){$episode06Inventory;return}
if($env:BLUSTONE_RESOURCE_ASSET_NAMES -ne ',' -or $env:BLUSTONE_RESOURCE_ASSET_GLOB){throw 'Restore complete separate E05 selection first'}
foreach($episode06Required in @('UI_ITEM.jet','C012.jet','C036.jet','M008.jet','C030.jet','UI_SHOP.jet','C017.jet','CUT_E0401.jet')){
 if(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',') -notcontains $episode06Required){throw "Missing prior original: $episode06Required"}
}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $episode06Assets).Path
$env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',')+$episode06Hashes.Keys)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634682'
$env:BLUSTONE_RESLIST_STAMP='1634682'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634682'
Write-Output 'Complete original E06 separate materials selected, stamp1634682; native validation pending. Original duplicate Karl rows preserved, native first index wins.'
