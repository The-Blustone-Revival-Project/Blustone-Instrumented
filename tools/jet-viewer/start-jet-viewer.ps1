param(
    [string]$Root,
    [int]$Port = 8765
)

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

$viewer = Join-Path $Root 'tools\jet-viewer\jet_viewer.py'
$bundledPython = Join-Path $Root 'tools\python-venv\Scripts\python.exe'

if (Test-Path -LiteralPath $bundledPython) {
    & $bundledPython $viewer --root $Root --port $Port
    exit $LASTEXITCODE
}

$python = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $python) {
    & $python.Source -3 $viewer --root $Root --port $Port
    exit $LASTEXITCODE
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $python) {
    & $python.Source $viewer --root $Root --port $Port
    exit $LASTEXITCODE
}

throw 'Python 3 was not found. Install Python 3.10+ or restore tools\python-venv.'

