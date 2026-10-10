# Original E02 dialogue, Bright, monsters and environment2. Source after all
# E01/fishing/Bear/final-background overlays. No install/restart/state writes.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$episode02Root=Split-Path $PSScriptRoot -Parent
$episode02Assets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $episode02Assets){$episode02Assets=Join-Path $episode02Root 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$episode02Hashes=[ordered]@{
 'DIAL_BG.jet'='b12aa44631bceb6da1d20870b8f84476b5922108dfe48c4248637a466148043e'
 'DIAL_BG9.jet'='f085326e3139884fce5e1e2332312885c6aa15bf5dc6d4edf66cda4dc1c85b03'
 'C007_SND.jet'='5e794d5014e333b74927bb508d259cd2b1f78653248379f8e3ca839f4560248c'
 'C032_SND.jet'='0e6047ccd0490e0d217493ac473ddfbf634817ba4eba4358eb2b420d86d8cab3'
 'C054_SND.jet'='b43abdae9f8ef2f86e5536602888f6f62dda8b484484b33c787b351c7841255a'
 'CUT_E0201.jet'='ca39470995f008e4eac95485b26621da2235a9626e7964b6d8b4f57bb7825fb5'
 'N500.jet'='a362f88ce48fb503dc035de13f446854282d43e75478cff6def375a2998d7f5c'
 'N501.jet'='fb76b2c0a27cde2d257dc493c4603049bbae49436ab21c8028a25d8c4ffd4053'
 'N002.jet'='cfd0b67b718d7ace8efa082b0fee9e1cc032aac5ca561aec32e6927ee3d88ae1'
 'C049.jet'='af47cd8414e302aed6bfcbf2edfc6338e529e25258441fc9d216290d9e0af88d'
 'C049_Q.jet'='4e3e5638bd74f83acc9c722be8b1ad3ea6ab9790a6bcb4f08d791a0cabbd3940'
 'C049_EFT.jet'='8d15176a68eaa4544b9995c349a281bdd699302984e8d5adacd4bcad4919100f'
 'C049_SND.jet'='4e2525e491ba24839edc963705bd106e0f6ca67d3bbff77d8fd2d8ca687c9564'
 'M017.jet'='cf7dae6ce9b3b44fa673d4abfa52030f651264463beae2d0484be6a525f0f1bb'
 'M021.jet'='3c623ebdcfc2db86b66ddabcd09be8d08c008335286e1494dbbfdd8ef78dd328'
 'ST002.jet'='e75a9e7be84632e960a3084e4262726604c013d96633c3015d125f9ada9129ba'
 'VOICE_CDN5.jet'='87f5652c06de9e81922270636222031c7332088c777ee3accc0c8e6df21e14aa'
 'VOICE_CDN8.jet'='e31df9f7ab1693d0350b967f48c4b93a67e82624e93770d00386540036092d8b'
 'VOICE_CDN9.jet'='ecd78b8d0b317cc088d7b11920c0e5b18fc638b947f55c15134d3f1006beab6f'
}
$episode02Voices=@('VOICE_CDN5.jet','VOICE_CDN8.jet','VOICE_CDN9.jet')
$episode02Inventory=@(foreach($episode02Entry in $episode02Hashes.GetEnumerator()){
 $episode02File=Join-Path $episode02Assets $episode02Entry.Key
 if(-not(Test-Path -LiteralPath $episode02File -PathType Leaf)){throw "Missing original E02 pack: $($episode02Entry.Key)"}
 $episode02Hash=(Get-FileHash -LiteralPath $episode02File -Algorithm SHA256).Hash.ToLowerInvariant()
 if($episode02Hash -ne $episode02Entry.Value){throw "Original E02 pack hash changed: $($episode02Entry.Key)"}
 if($episode02Voices -contains $episode02Entry.Key){
  $episode02PackageRoots=@((Join-Path $episode02Root 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique
  foreach($episode02PackageRoot in $episode02PackageRoots){
   $episode02Bundled=Join-Path $episode02PackageRoot $episode02Entry.Key
   if(Test-Path -LiteralPath $episode02Bundled){
    if(-not(Test-Path -LiteralPath $episode02Bundled -PathType Leaf) -or
      (Get-FileHash -LiteralPath $episode02Bundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode02Hash){throw "Bundled E02 voice conflicts: $($episode02Entry.Key)"}
   }
  }
 }
 [pscustomobject]@{Name=$episode02Entry.Key;Bytes=(Get-Item -LiteralPath $episode02File).Length;SHA256=$episode02Hash}
})
if($InspectOnly){$episode02Inventory;return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore explicit prior resource selections first'}
foreach($episode02Required in @('M008.jet','UI_SHOP.jet','C036.jet','CUT_E0101.jet','DIAL_BG2.jet')){
 if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains $episode02Required){throw "Restore previous original overlay: $episode02Required"}
}
$episode02Folded=@($episode02Hashes.Keys|Where-Object{$_ -notin $episode02Voices})
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $episode02Assets).Path
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+$episode02Folded)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',')+$episode02Voices)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634672'
$env:BLUSTONE_RESLIST_STAMP='1634672'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634672'
Write-Output 'Original E02 material profile prepared, stamp1634672; restart separately. Native residency pending.'
