# Source this before start-server.ps1 for the pending native Episode test.
# It selects original public packs; no APK changes, downloads, or server restart.
# -InspectOnly validates files without changing environment variables.
# Native story playback and generated C003_DIALOG binding remain unverified.
param([switch]$InspectOnly, [switch]$SeparatePackages)
$ErrorActionPreference = 'Stop'
$episodeRoot = Split-Path $PSScriptRoot -Parent
$episodeAssetRoot = $env:BLUSTONE_RESOURCE_ASSET_DIR
if (-not $episodeAssetRoot) {
    $episodeAssetRoot = Join-Path $episodeRoot 'recovered-assets\phone-2026-09-18\extracted\split_PADResource\assets'
}
$episodeAssetRoot = (Resolve-Path -LiteralPath $episodeAssetRoot).Path
$episodePacks = @(
    'R_EPISODE.jet', 'EPISODE.jet', 'DIAL-EN.jet', 'N001_BG.jet', 'ST099.jet',
    'SND1.jet', 'SND_CDN.jet', 'VOICE_CDN2.jet', 'VOICE_CDN6.jet',
    'C009.jet', 'C009_Q.jet', 'C009_EFT.jet', 'C009_SND.jet'
)
$episodeInventory = @($episodePacks | ForEach-Object {
    $episodeFile = Join-Path $episodeAssetRoot $_
    if (-not (Test-Path -LiteralPath $episodeFile -PathType Leaf)) { throw "Required original Episode pack missing: $_" }
    $episodeSize = (Get-Item -LiteralPath $episodeFile).Length
    if ($episodeSize -lt 24) { throw "Invalid Episode pack size: $_" }
    [pscustomobject]@{ Name = $_; Bytes = $episodeSize; SHA256 = (Get-FileHash -LiteralPath $episodeFile -Algorithm SHA256).Hash.ToLowerInvariant() }
})
if ($InspectOnly) { $episodeInventory; return }

# Preserve the established battle profile and any explicitly selected extra packs.
if ($SeparatePackages) {
    # Move only the Episode additions to distinct packages; preserve unrelated
    # folded selections. Cached client files are deliberately not removed.
    if ($env:BLUSTONE_RESOURCE_ASSET_GLOB) {
        throw 'Separate Episode profile requires an empty BLUSTONE_RESOURCE_ASSET_GLOB to avoid dual delivery.'
    }
    $env:BLUSTONE_RESOURCE_ASSET_DIR = $episodeAssetRoot
    foreach ($selectionName in @('BLUSTONE_RESOURCE_ASSET_NAMES', 'BLUSTONE_RESOURCE_ASSET_NAMES_EXTRA')) {
        $selectionValue = [Environment]::GetEnvironmentVariable($selectionName)
        if ($selectionValue) {
            $filteredSelection = @($selectionValue -split ',' | Where-Object { $_ -and $_.Trim() -notin $episodePacks }) -join ','
            [Environment]::SetEnvironmentVariable($selectionName, $filteredSelection)
        }
    }
    $env:BLUSTONE_PACKAGE_NAMES_EXTRA = (@(($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',') + $episodePacks) |
        Where-Object { $_ } | Select-Object -Unique) -join ','
    $env:BLUSTONE_RESOURCE_VERSION = '1634666'
    $env:BLUSTONE_RESLIST_STAMP = '1634666'
    $env:BLUSTONE_RESLIST_HEADER_STAMP = '1634666'
    Write-Output 'Separate Episode research profile prepared: 13 original packages, stamp1634666. Native acceptance unverified; start/restart separately.'
    return
}
$env:BLUSTONE_RESOURCE_ASSET_DIR = $episodeAssetRoot
Write-Warning 'The folded59-asset Episode profile aborted bootstrap on +9 and +10. Use -SeparatePackages for the pending smaller-package experiment; native acceptance remains unverified.'
$env:BLUSTONE_PACKAGE_NAMES_EXTRA = (@($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',' |
    Where-Object { $_ -and $_.Trim() -notin $episodePacks }) -join ',')
$env:BLUSTONE_RESOURCE_ASSET_NAMES_EXTRA = (@(($env:BLUSTONE_RESOURCE_ASSET_NAMES_EXTRA -split ',') + $episodePacks) |
    Where-Object { $_ } | Sort-Object -Unique) -join ','
if ($env:BLUSTONE_RESOURCE_ASSET_NAMES) {
    $env:BLUSTONE_RESOURCE_ASSET_NAMES = (@(($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',') + $episodePacks) |
        Where-Object { $_ } | Sort-Object -Unique) -join ','
}
$env:BLUSTONE_RESOURCE_VERSION = '1634664'
$env:BLUSTONE_RESLIST_STAMP = '1634664'
$env:BLUSTONE_RESLIST_HEADER_STAMP = '1634664'
Write-Output "Episode research profile prepared: 13 original packs, resource stamp1634664. Start/restart the replica separately. Native playback unverified."
