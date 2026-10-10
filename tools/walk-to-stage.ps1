# Walk the Blustone client from the village into the expedition stage map.
#
# The path is fixed now that GetBaseInfo advertises the url_list keys the
# launcher resolves, so it is scripted rather than tapped by hand each time.
# Every step is verified by screenshot rather than assumed.
#
#   .\tools\walk-to-stage.ps1 [-Serial 127.0.0.1:5555] [-Pause <seconds>]
param(
    [string]$Serial = '127.0.0.1:5555',
    [int]$Pause = 6
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'env.ps1') | Out-Null

$shotDir = Join-Path $root 'analysis'
$stamp = Get-Date -Format 'yyyy-MM-dd-HHmmss'

function Tap([int]$x, [int]$y, [string]$label, [int]$wait = $Pause) {
    adb -s $Serial shell input tap $x $y | Out-Null
    Start-Sleep -Seconds $wait
    $file = Join-Path $shotDir "walk-$stamp-$label.png"
    cmd /c "adb -s $Serial exec-out screencap -p > `"$file`"" | Out-Null
    Write-Output "  tap ($x,$y) -> $label"
    return $file
}

Write-Output "walking to the stage map on $Serial"
# A fresh launch shows the "Data download / 23 mb / Yes" modal before the village
# is reachable. It is not shown on every launch, so tap Yes and let the client
# settle whether or not it was there.
Tap 540 1180 'data-download-yes' 10 | Out-Null
Tap 400 660 'village-airport' 10 | Out-Null          # Airport building
Tap 540 1450 'airport-dialog' 7 | Out-Null          # advance Isla's greeting
Tap 490 1345 'airport-cruise' 14 | Out-Null         # "Well, to cruise, of course!"
Tap 635 1035 'expedition-snowfield' 12 | Out-Null   # Snowfield node
# Select a chapter shield, then enter the stage's battle preparation. The map
# layout shifted once the stage table populated (progress now reads 3/9 and the
# node labels 3/6/9), so the shield sits lower than before.
Tap 290 1640 'map-select-shield' 8 | Out-Null
Tap 700 1700 'map-enter-battle' 10 | Out-Null
Write-Output "done - screenshots under analysis\walk-$stamp-*.png"
