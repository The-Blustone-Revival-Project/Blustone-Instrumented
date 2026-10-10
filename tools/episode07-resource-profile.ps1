# Complete original E07 combat, portrait and stage materials. Source after
# complete separate E06 + UI_ITEM profile; no install/restart/grants/stat edits.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$episode07Root=Split-Path $PSScriptRoot -Parent
$episode07Assets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $episode07Assets){$episode07Assets=Join-Path $episode07Root 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$episode07Hashes=[ordered]@{
 'C007.jet'='949be5dbd4d6451f4f50fc862a1a0f5071f591fda73e95da3a5d727690930e73'
 'C007_EFT.jet'='8bb0c0971a56491cb3e41cd9b4279e077e295d9f1fd33919a6bbb537e9e0af3e'
 'C007_Q.jet'='8395cc442c9a41a4381766e5c8b959e6d89f8cc86ba6146efc024ceeb07192b8'
 'C011.jet'='e2aea670ac617df79be05ad2c860074997efbd5201c1a8724e179d8bca1be944'
 'C011_EFT.jet'='268de72b2d4e405009a7345f9c0a536d131b154194b03e9f029497e7880c88ed'
 'C011_Q.jet'='6abe741c5b180e20d6a96d171320294e978e4780d6d1cd69504ed94a978f3a41'
 'C011_SND.jet'='0cb28a36f329a90661c41bc0619258b1d03c0cfff3956187ea670dead89c5ac5'
 'C016.jet'='c35c525e4eb65a7ded346aa7baac2aacdafbc40d51c38a746debebf3d2c2436f'
 'C016_EFT.jet'='f1347d403ac57aa855841b2307d0f596754a5c6b8dd198fc1a1abf601228c41f'
 'C016_Q.jet'='33b1e5a313ad84c990a0bbb5335304fe84bf64aaed8e12db72fb94060e073eb4'
 'C016_SND.jet'='f578b51dbf267d304a34963ec906b0eaa372486c1f2fad0c55dd68e5f4ff6f6a'
 'C018.jet'='7ab656845ab2e37448c48e073ec34301fe5d5e9dd505c384d200a4c25d95e82a'
 'C018_EFT.jet'='a19f6f9e06468eb1c2f5ecf6b861d1e9e78c57bee6f2fef5831c7f8a1ac29181'
 'C018_Q.jet'='9eae7a673078dc1baf46c66ea935ad94f13fc48507e155197b39744a1ea57fba'
 'M020.jet'='f0acad2194ab843a3fb722176c51c93a916fab8238be19aa42ac379097e62dbb'
 'N007.jet'='48633922e7091be83983fdff41416725f14c1631a09fac03986d17b31f9a45c7'
 'ST901.jet'='5036d6f3490eb011a0b7fc3bcb30bd56e897dc776657e11d9543f995f9725128'
}
$episode07Sizes=[ordered]@{
 'C007.jet'=753975
 'C007_EFT.jet'=2137495
 'C007_Q.jet'=57482
 'C011.jet'=1189575
 'C011_EFT.jet'=1944752
 'C011_Q.jet'=53700
 'C011_SND.jet'=86588
 'C016.jet'=757670
 'C016_EFT.jet'=7335026
 'C016_Q.jet'=120442
 'C016_SND.jet'=135066
 'C018.jet'=900296
 'C018_EFT.jet'=1147675
 'C018_Q.jet'=42481
 'M020.jet'=925674
 'N007.jet'=3327702
 'ST901.jet'=663573
}
$episode07Inventory=@(foreach($episode07Entry in $episode07Hashes.GetEnumerator()){
 $episode07File=Join-Path $episode07Assets $episode07Entry.Key
 if(-not(Test-Path -LiteralPath $episode07File -PathType Leaf) -or
   (Get-Item -LiteralPath $episode07File).Length -ne $episode07Sizes[$episode07Entry.Key] -or
   (Get-FileHash -LiteralPath $episode07File -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode07Entry.Value){throw "Original E07 pack missing/changed: $($episode07Entry.Key)"}
 foreach($episode07PackageRoot in @((Join-Path $episode07Root 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique){
  $episode07Bundled=Join-Path $episode07PackageRoot $episode07Entry.Key
  if((Test-Path -LiteralPath $episode07Bundled) -and
    (-not(Test-Path -LiteralPath $episode07Bundled -PathType Leaf) -or
     (Get-FileHash -LiteralPath $episode07Bundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $episode07Entry.Value)){throw "Bundled E07 conflict: $($episode07Entry.Key)"}
 }
 [pscustomobject]@{Name=$episode07Entry.Key;Bytes=(Get-Item -LiteralPath $episode07File).Length;SHA256=$episode07Entry.Value}
})
if($InspectOnly){$episode07Inventory;return}
if($env:BLUSTONE_RESOURCE_ASSET_NAMES -ne ',' -or $env:BLUSTONE_RESOURCE_ASSET_GLOB){throw 'Restore complete separate E06 selection first'}
foreach($episode07Required in @('UI_ITEM.jet','C012.jet','C036.jet','M008.jet','C030.jet','UI_SHOP.jet','C017.jet','CUT_E0401.jet','C040.jet','C040_EFT.jet','C040_Q.jet','C040_SND.jet','C054.jet')){
 if(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',') -notcontains $episode07Required){throw "Missing prior original: $episode07Required"}
}
$episode07Existing=@($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ','|ForEach-Object{$_.Trim()}|Where-Object{$_})
$episode07Added=@($episode07Hashes.Keys|Where-Object{$_ -notin $episode07Existing})
$episode07MaxStamp=1634683L # Current complete E06/native CDN migration baseline.
foreach($episode07StampName in @('BLUSTONE_RESOURCE_VERSION','BLUSTONE_RESLIST_STAMP','BLUSTONE_RESLIST_HEADER_STAMP')){
 $episode07StampText=[Environment]::GetEnvironmentVariable($episode07StampName)
 $episode07ParsedStamp=0L
 if($episode07StampText -notmatch '^[1-9][0-9]*$' -or -not [long]::TryParse($episode07StampText,[ref]$episode07ParsedStamp) -or $episode07ParsedStamp -gt [int]::MaxValue){throw "Invalid prior CDN stamp: $episode07StampName"}
 $episode07MaxStamp=[Math]::Max($episode07MaxStamp,$episode07ParsedStamp)
}
# New manifest content must advance every advertised stamp together. Re-sourcing
# an already selected E07 profile is idempotent; old stamp1634683 is corrected.
$episode07NextStamp=[Math]::Max(1634684L,$episode07MaxStamp+[long]($episode07Added.Count -gt 0))
if($episode07NextStamp -gt [int]::MaxValue){throw 'E07 CDN stamp exceeds this profile tool signed 32-bit stamp policy'}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $episode07Assets).Path
$env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',')+$episode07Hashes.Keys)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION=[string]$episode07NextStamp
$env:BLUSTONE_RESLIST_STAMP=[string]$episode07NextStamp
$env:BLUSTONE_RESLIST_HEADER_STAMP=[string]$episode07NextStamp
Write-Output "Complete original E07 separate materials selected, stamp$episode07NextStamp ($($episode07Added.Count) new packs); native validation pending. Original stats and CERUM01 reward metadata remain unchanged."
