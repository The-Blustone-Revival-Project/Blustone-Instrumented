# Original E01 Story05/06 voices, Bear actor and win cut-in. Source AFTER
# fishing, Story04 and Veteran overlays. No restart/install/state mutation.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$bearRoot=Split-Path $PSScriptRoot -Parent
$bearAssets=$env:BLUSTONE_RESOURCE_ASSET_DIR
if(-not $bearAssets){$bearAssets=Join-Path $bearRoot 'recovered-assets/phone-2026-09-18/extracted/split_PADResource/assets'}
$bearHashes=[ordered]@{
  'C036.jet'='e4f7cb46ab924b75f173752a0696e72c8288534273ca8f6104529b08c656b360'
  'C036_Q.jet'='73002b5ee10b3dd49e5647531b142fb4fff410ab11cf8a99f6386d031e4baa25'
  'C036_EFT.jet'='b3a0a27dfdb4f79b1119cc27591ec768303a0209a85c1b0f66247d5fe38ddb83'
  'C036_SND.jet'='d4f8ff00e412c6f0515ba8caf61351b88e20769deebf882fff9ff7ca13f9ce02'
  'VOICE_CDN1.jet'='a04b9a3098d9142b09492089eb64e5e3475c32caaa5b299359cb25e31851f83b'
  'VOICE_CDN4.jet'='d1ea1fce10dbec7c8467980dd3be164f864c3717498c73e6d12c83f36443ef5d'
  'VOICE_CDN7.jet'='c40c97dc28a858a06882f6aa6fa9e8da9e75ef0ef5f430a20d59f8e09156608b'
  'CUT_E0101.jet'='32b1d7cc27c180bb4e814447974930a7ba1c7768f7a008b2625dbafb6a9e6e92'
}
$bearVoices=@('VOICE_CDN1.jet','VOICE_CDN4.jet','VOICE_CDN7.jet')
$bearInventory=@(foreach($bearEntry in $bearHashes.GetEnumerator()){
  $bearFile=Join-Path $bearAssets $bearEntry.Key
  if(-not(Test-Path -LiteralPath $bearFile -PathType Leaf)){throw "Missing original Bear/story pack: $($bearEntry.Key)"}
  $bearHash=(Get-FileHash -LiteralPath $bearFile -Algorithm SHA256).Hash.ToLowerInvariant()
  if($bearHash -ne $bearEntry.Value){throw "Original Bear/story pack hash changed: $($bearEntry.Key)"}
  # Separate-package resolution prefers PACKAGE_DIR to ASSET_DIR. Refuse a
  # different bundled voice rather than silently deliver a historical variant.
  if($bearVoices -contains $bearEntry.Key){
    # start-server.ps1 sets the canonical directory even when the current
    # shell advertises another one; validate both possible precedence roots.
    $bearPackageRoots=@((Join-Path $bearRoot 'analysis/runtime-package-full'),$env:BLUSTONE_PACKAGE_DIR)|Where-Object{$_}|Select-Object -Unique
    foreach($bearPackageRoot in $bearPackageRoots){
      $bearBundled=Join-Path $bearPackageRoot $bearEntry.Key
      if(Test-Path -LiteralPath $bearBundled){
        if(-not(Test-Path -LiteralPath $bearBundled -PathType Leaf) -or
           (Get-FileHash -LiteralPath $bearBundled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $bearHash){
          throw "Bundled voice conflicts with original PAD: $($bearEntry.Key)"
        }
      }
    }
  }
  [pscustomobject]@{Name=$bearEntry.Key;Bytes=(Get-Item -LiteralPath $bearFile).Length;SHA256=$bearHash}
})
if($InspectOnly){$bearInventory;return}
if($env:BLUSTONE_RESOURCE_ASSET_GLOB -or -not $env:BLUSTONE_RESOURCE_ASSET_NAMES){throw 'Restore the explicit established folded asset selection first'}
foreach($bearRequired in @('M008.jet','UI_SHOP.jet')){
  if(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') -notcontains $bearRequired){throw "Restore prior original material overlay: $bearRequired"}
}
$env:BLUSTONE_RESOURCE_ASSET_DIR=(Resolve-Path -LiteralPath $bearAssets).Path
$bearFolded=@('C036.jet','C036_Q.jet','C036_EFT.jet','C036_SND.jet','CUT_E0101.jet')
$env:BLUSTONE_RESOURCE_ASSET_NAMES=(@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')+$bearFolded)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_PACKAGE_NAMES_EXTRA=(@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',')+$bearVoices)|ForEach-Object{$_.Trim()}|Where-Object{$_}|Select-Object -Unique)-join ','
$env:BLUSTONE_RESOURCE_VERSION='1634670'
$env:BLUSTONE_RESLIST_STAMP='1634670'
$env:BLUSTONE_RESLIST_HEADER_STAMP='1634670'
Write-Output 'Original Story05/06 Bear/voices/cut-in profile prepared, stamp1634670; restart separately. Native residency pending.'
