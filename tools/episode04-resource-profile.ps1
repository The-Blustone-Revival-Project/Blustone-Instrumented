# Original E04 Lapis combat and Locke/Dumble dialogue portraits. Source after all
# previous overlays through episode03. C014/C048 portraits only; no grants.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$episode04Root=Split-Path $PSScriptRoot -Parent
$episode04Assets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $episode04Assets){$episode04Assets=Join-Path $episode04Root 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$episode04Hashes=[ordered]@{
 'C014.jet'='f3e8c809407139685e06c7790ca5873c6ba77d2700d6977081bd672a31f763ca'
 'C017.jet'='e0d08b1d07c526b41d5ea3c95438c834e9875ca5110d4f74fc54bb15e3a56975'
 'C017_EFT.jet'='800907c131ac6d9a7f5a530dbbc8edacc2511b59bb50d78fe83c690970aa941f'
 'C017_Q.jet'='6c773754a1242733743da0554a35184e7b361c6da576bfae12c1da1f2de6728b'
 'C017_SND.jet'='91c1fcc9fa21fafc5fac75b4b93edebbf22e4327aff989b1a1503987b279416c'
 'C048.jet'='f09f52954868d42a467e9d591204d8381a0cb6daff8cef6037dad17f398392ce'
}
$episode04Inventory=@(foreach($episode04Entry in $episode04Hashes.GetEnumerator()){
 $episode04File=Join-Path $episode04Assets $episode04Entry.Key
 if(-not(Test-Path -LiteralPath $episode04File -PathType Leaf)){throw "Missing original E04 pack: $($episode04Entry.Key)"}
 $episode04Hash=(Get-FileHash -LiteralPath $episode04File -Algorithm SHA256).Hash.ToLowerInvariant()
 if($episode04Hash -ne $episode04Entry.Value){throw "Original E04 pack hash changed: $($episode04Entry.Key)"}
 [pscustomobject]@{Name=$episode04Entry.Key;Bytes=(Get-Item -LiteralPath $episode04File).Length;SHA256=$episode04Hash}
})
if($InspectOnly){$episode04Inventory;return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore explicit prior resource selections first'}
foreach($episode04Required in @('M008.jet','UI_SHOP.jet','C036.jet','CUT_E0101.jet','DIAL_BG2.jet','C049.jet','ST002.jet','CUT_E0201.jet','C013.jet','C010.jet','ST003.jet')){
 if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains $episode04Required){throw "Restore previous original overlay: $episode04Required"}
}
$episode04Folded=@($episode04Hashes.Keys)
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $episode04Assets).Path
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+$episode04Folded)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634674'
$env:BLUSTONE_RESLIST_STAMP='1634674'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634674'
Write-Output 'Original E04 material profile prepared, stamp1634674; restart separately. Native residency pending.'
