# Experimental original E05 material selection; full folded/separate layouts
# and C030-only folded selection failed native bootstrap with bad_alloc.
# InspectOnly is safe for normal inventory work.
# Source after episode04 and prior overlays; no install/restart/grants.
param([switch]$InspectOnly,[switch]$Experimental,
 [ValidateSet('All','AcerolaOnly','CompleteSeparate')][string]$Selection='All')
$ErrorActionPreference='Stop'
$episode05Root=Split-Path $PSScriptRoot -Parent
$episode05Assets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $episode05Assets){$episode05Assets=Join-Path $episode05Root 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$episode05Hashes=[ordered]@{
 'C012.jet'='308bd36707873b09fb750baf3fe1c1830458521b01cd90eb5f838b3a4cce7f57'
 'C012_EFT.jet'='d6cbe39b9da296f5ba6271e08a89d87d945eb0d9e3833563ad7d26f59a019bd2'
 'C012_Q.jet'='37b022a9949b6a2ec16df563522e416cfe0f90652aae47ceb21c2f81d389fa4b'
 'C012_SND.jet'='9f660ea0374ce7423c70c3924a583d6f0ee1ae4aac6899ef0bdac8a335629add'
 'C030.jet'='f997f429d8fce9ac8631cb9208e12da6eb6c19541e545fd840a69d05866d94fb'
 'CUT_E0401.jet'='9b1d133c8562c446d799c85a45eb73f9a338a42fa75eb9bff746db6dfb5e4ee6'
 'M016.jet'='ab40de921dec9d9f5fcb292870534dc3c37f88443067dccd5d6b4de2c38061f2'
 'M018.jet'='6c77291f4918548fb777c982e86d9bd67b4b3c920622271782693d76da0490ae'
 'N001.jet'='a54b3997bf8f2b60f4a0ae787d9a926c2a9188f0fb6661f1e153e3b4cc9cb6e8'
}
$episode05Inventory=@(foreach($episode05Entry in $episode05Hashes.GetEnumerator()){
 $episode05File=Join-Path $episode05Assets $episode05Entry.Key
 if(-not(Test-Path -LiteralPath $episode05File -PathType Leaf)){throw "Missing original E05 pack: $($episode05Entry.Key)"}
 $episode05Hash=(Get-FileHash -LiteralPath $episode05File -Algorithm SHA256).Hash.ToLowerInvariant()
 if($episode05Hash -ne $episode05Entry.Value){throw "Original E05 pack hash changed: $($episode05Entry.Key)"}
 foreach($episode05PackageRoot in @((Join-Path $episode05Root 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique){
  $episode05Bundled=Join-Path $episode05PackageRoot $episode05Entry.Key
  if(Test-Path -LiteralPath $episode05Bundled){
   if(-not(Test-Path -LiteralPath $episode05Bundled -PathType Leaf) -or
     (Get-FileHash -LiteralPath $episode05Bundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode05Hash){throw "Bundled E05 original conflicts: $($episode05Entry.Key)"}
  }
 }
 [pscustomobject]@{Name=$episode05Entry.Key;Bytes=(Get-Item -LiteralPath $episode05File).Length;SHA256=$episode05Hash}
})
if($InspectOnly){$episode05Inventory;return}
if(-not $Experimental){throw 'E05 full and C030-only selections failed bootstrap with bad_alloc; use -InspectOnly or explicit -Experimental for controlled diagnosis'}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore explicit prior resource selections first'}
foreach($episode05Required in @('M008.jet','UI_SHOP.jet','C036.jet','CUT_E0101.jet','DIAL_BG2.jet','C049.jet','ST002.jet','CUT_E0201.jet','C013.jet','C010.jet','ST003.jet','C017.jet','C014.jet','C048.jet','M021.jet')){
 if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains $episode05Required){throw "Restore previous original overlay: $episode05Required"}
}
$episode05PriorFolded=@($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ','|ForEach-Object{$_.Trim()}|Where-Object{$_ -and $_ -notin $episode05Hashes.Keys}|Select-Object -Unique)
# Validate the full relocation before changing any selections. Preserve every
# prior E04 payload and all nine E05 originals; this is not a smaller catalog.
if($Selection -eq 'CompleteSeparate'){
 if($episode05PriorFolded.Count -ne 88){throw 'CompleteSeparate requires the full 88-asset E04 selection'}
 foreach($episode05Name in $episode05PriorFolded){
  if($episode05Name -notmatch '^[A-Za-z0-9_.-]+\.jet$'){throw "Invalid prior asset basename: $episode05Name"}
  $episode05Original=Join-Path $episode05Assets $episode05Name
  if(-not(Test-Path -LiteralPath $episode05Original -PathType Leaf)){throw "Missing prior original: $episode05Name"}
  $episode05OriginalHash=(Get-FileHash -LiteralPath $episode05Original -Algorithm SHA256).Hash
  foreach($episode05PackageRoot in @((Join-Path $episode05Root 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique){
   $episode05Bundled=Join-Path $episode05PackageRoot $episode05Name
   if((Test-Path -LiteralPath $episode05Bundled) -and
     (-not(Test-Path -LiteralPath $episode05Bundled -PathType Leaf) -or
      (Get-FileHash -LiteralPath $episode05Bundled -Algorithm SHA256).Hash -ne $episode05OriginalHash)){throw "Prior original conflicts with package root: $episode05Name"}
  }
 }
}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $episode05Assets).Path
# Keep all nine originals, but preserve the known88-asset E_NEW payload after
# the97-asset folded bootstrap aborted with bad_alloc (cause remains unproved).
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')|ForEach-Object{$_.Trim()}|Where-Object{$_ -and $_ -notin $episode05Hashes.Keys}|Select-Object -Unique)-join ','
$episode05PriorPackages=@($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ','|ForEach-Object{$_.Trim()}|Where-Object{$_ -and $_ -notin $episode05Hashes.Keys}|Select-Object -Unique)
if($Selection -eq 'CompleteSeparate'){
 $env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@($episode05PriorPackages+$episode05PriorFolded+$episode05Hashes.Keys)|Select-Object -Unique)-join ','
 # Nonempty explicit empty list: launcher skips defaults; native server filters
 # empty names. The E_NEW base tree/UI delta is still served unchanged.
 $env:BLUSTONE_RESOURCE_ASSET_NAMES=','
 $episode05Stamp='1634680'
 Write-Output 'EXPERIMENTAL complete separate profile: all88 prior assets plus9 E05 originals retained, zero additional E_NEW folding. Native validation pending.'
}elseif($Selection -eq 'AcerolaOnly'){
 $env:BLUSTONE_RESOURCE_ASSET_NAMES+=',C030.jet'
 $env:BLUSTONE_PACKAGE_NAMES_EXTRA=$episode05PriorPackages -join ','
 $episode05Stamp='1634678'
 Write-Output 'EXPERIMENTAL C030-only folded selection; this layout previously failed bootstrap. Restart separately only for diagnosis.'
}else{
 $env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@($episode05PriorPackages+$episode05Hashes.Keys)|Select-Object -Unique)-join ','
 $episode05Stamp='1634676'
 Write-Output 'EXPERIMENTAL E05 separate-pack profile; this layout previously failed bootstrap. Restart separately only for diagnosis.'
}
$env:BLUSTONE_RESOURCE_VERSION=$episode05Stamp
$env:BLUSTONE_RESLIST_STAMP=$episode05Stamp
$env:BLUSTONE_RESLIST_HEADER_STAMP=$episode05Stamp
