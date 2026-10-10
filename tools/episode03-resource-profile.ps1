# Original E03 dialogue, Denali/Vincent and environment3. Source after all
# E01/fishing/Bear/E02 overlays. C018 sound dependency only; no grants.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$episode03Root=Split-Path $PSScriptRoot -Parent
$episode03Assets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $episode03Assets){$episode03Assets=Join-Path $episode03Root 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$episode03Hashes=[ordered]@{
 'C010.jet'='3592c448aca8b7096f4adde8420e2ef19988cc6e452c23ef513f0e4fc6c59067'
 'C010_EFT.jet'='692d3a46d7eddf39fb9b526b713d171c9e79d1b250e6408aa231bf62d87eb797'
 'C010_Q.jet'='f2a19358c627047df72baa8329428147e70f8a0d36960b1e0a3996301985955d'
 'C010_SND.jet'='e32a4e85807a49e2961ebc5de7b178295c9c818c20816df92f85528ba1879df9'
 'C013.jet'='be6a19cabdbecc1487fd2ba82588560c62de481012f398cbba78452862224733'
 'C013_EFT.jet'='4b673e0b3e3f84383629cb19d20ffcd04ada5bb25de6344714275c1dca662911'
 'C013_Q.jet'='1a09892b4e9ac4809b83e9e60a54f768d790caf98024677e85726eba8dd8d583'
 'C013_SND.jet'='e46aa30fe6afc99b3ef9172a4aaa0fa3ebc3d1b499839e87a34f4cc2f6ba59ed'
 'C018_SND.jet'='e1b1ffaeb0dd44c9a01a87c1f225097ab99cef553b3bfb496d6643d244c1bf3d'
 'CUT_E0301.jet'='e051215d2cf65bf1340279e175cce955020d7484af2188ae485b90c3583a63f8'
 'N004.jet'='dac953f788f16936f95c664cb9fd28e628f24b3325a7dc241a19b658e86935bb'
 'ST003.jet'='a58c3a55a0b89c4beaf73bc46babac9b837874c5dabad88bc1b7c099fcd87e61'
 'VOICE_CDN3.jet'='3fd64cf3530ca00f74c04245e103c008f2c0fe385a992f11b3dfbf2072558ea0'
}
$episode03Voices=@('VOICE_CDN3.jet')
$episode03Inventory=@(foreach($episode03Entry in $episode03Hashes.GetEnumerator()){
 $episode03File=Join-Path $episode03Assets $episode03Entry.Key
 if(-not(Test-Path -LiteralPath $episode03File -PathType Leaf)){throw "Missing original E03 pack: $($episode03Entry.Key)"}
 $episode03Hash=(Get-FileHash -LiteralPath $episode03File -Algorithm SHA256).Hash.ToLowerInvariant()
 if($episode03Hash -ne $episode03Entry.Value){throw "Original E03 pack hash changed: $($episode03Entry.Key)"}
 if($episode03Voices -contains $episode03Entry.Key){
  $episode03PackageRoots=@((Join-Path $episode03Root 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique
  foreach($episode03PackageRoot in $episode03PackageRoots){
   $episode03Bundled=Join-Path $episode03PackageRoot $episode03Entry.Key
   if(Test-Path -LiteralPath $episode03Bundled){
    if(-not(Test-Path -LiteralPath $episode03Bundled -PathType Leaf) -or
      (Get-FileHash -LiteralPath $episode03Bundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode03Hash){throw "Bundled E03 voice conflicts: $($episode03Entry.Key)"}
   }
  }
 }
 [pscustomobject]@{Name=$episode03Entry.Key;Bytes=(Get-Item -LiteralPath $episode03File).Length;SHA256=$episode03Hash}
})
if($InspectOnly){$episode03Inventory;return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore explicit prior resource selections first'}
foreach($episode03Required in @('M008.jet','UI_SHOP.jet','C036.jet','CUT_E0101.jet','DIAL_BG2.jet','C049.jet','ST002.jet','CUT_E0201.jet')){
 if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains $episode03Required){throw "Restore previous original overlay: $episode03Required"}
}
$episode03Folded=@($episode03Hashes.Keys|Where-Object{$_ -notin $episode03Voices})
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $episode03Assets).Path
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+$episode03Folded)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',')+$episode03Voices)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634673'
$env:BLUSTONE_RESLIST_STAMP='1634673'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634673'
Write-Output 'Original E03 material profile prepared, stamp1634673; restart separately. Native residency pending.'
