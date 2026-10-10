param(
    [Parameter(Mandatory = $true)]
    [string]$InputNativeLibrary,

    [Parameter(Mandatory = $true)]
    [string]$OutputNativeLibrary,

    [string]$OldHost = 'pv-prd.vshower.com',
    [string]$NewHost = '10.0.2.2:8080'
)

$inputPath = (Resolve-Path -LiteralPath $InputNativeLibrary).Path
$outputPath = [IO.Path]::GetFullPath($OutputNativeLibrary)
$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$oldBytes = [Text.Encoding]::ASCII.GetBytes($OldHost)
$newBytes = [Text.Encoding]::ASCII.GetBytes($NewHost)
if ($newBytes.Length -gt $oldBytes.Length) {
    throw "Replacement host is longer than the original literal ($($newBytes.Length) > $($oldBytes.Length))."
}

$bytes = [IO.File]::ReadAllBytes($inputPath)
$matches = [Collections.Generic.List[int]]::new()
for ($i = 0; $i -le $bytes.Length - $oldBytes.Length; $i++) {
    $match = $true
    for ($j = 0; $j -lt $oldBytes.Length; $j++) {
        if ($bytes[$i + $j] -ne $oldBytes[$j]) {
            $match = $false
            break
        }
    }
    if ($match) {
        $matches.Add($i)
        $i += $oldBytes.Length - 1
    }
}

if ($matches.Count -ne 1) {
    throw "Expected exactly one '$OldHost' literal in '$inputPath'; found $($matches.Count)."
}

$offset = $matches[0]
for ($j = 0; $j -lt $oldBytes.Length; $j++) {
    $bytes[$offset + $j] = if ($j -lt $newBytes.Length) { $newBytes[$j] } else { 0 }
}

[IO.File]::WriteAllBytes($outputPath, $bytes)
$sha = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output "Patched $inputPath"
Write-Output "  literal: $OldHost -> $NewHost"
Write-Output "  offset: 0x$('{0:x}' -f $offset)"
Write-Output "  output: $outputPath"
Write-Output "  sha256: $sha"
