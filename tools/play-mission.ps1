# Walk the client from a cold launch into the battle and fire it.
#
#   .\tools\play-mission.ps1 [-Serial 127.0.0.1:5551] [-Shoot]
#
# One end-to-end attempt: launch, confirm the data-download modal, walk to the
# stage map, select the node that resolves a stage, and press Begin Battle.
#
# The node tap coordinates are discovered, not hard-coded: the map layout moves
# once the stage table populates, so the script probes candidate points and stops
# at the one that makes the client issue /reference/GetTargetStageMonster. That
# is the signal that a stage actually resolved, and it is also how the real
# stage_id gets read back off the wire via BLUSTONE_LOG_GAME_VALUES=1.

param(
    [string]$Serial = '127.0.0.1:5555',
    [switch]$Shoot
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'env.ps1') | Out-Null

$root = Split-Path $PSScriptRoot -Parent
$log = Join-Path $root 'server-ts\logs\server.stdout.log'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$shotDir = Join-Path $root 'analysis'

function Save-Shot([string]$name) {
    if (-not $Shoot) { return }
    $file = Join-Path $shotDir "play-$stamp-$name.png"
    cmd /c "adb -s $Serial exec-out screencap -p > `"$file`"" | Out-Null
    Write-Output "  screenshot: analysis\play-$stamp-$name.png"
}

function Count-Hits([string]$pattern) {
    if (-not (Test-Path $log)) { return 0 }
    return (Select-String -Path $log -Pattern $pattern | Measure-Object).Count
}

function Last-Line([string]$pattern) {
    if (-not (Test-Path $log)) { return '' }
    $m = Select-String -Path $log -Pattern $pattern | Select-Object -Last 1
    if ($m) { return $m.Line.Trim() }
    return ''
}

Write-Output "== relaunch =="
adb -s $Serial shell am force-stop com.vshower.prd_sr.instrumented | Out-Null
Start-Sleep -Seconds 2
adb -s $Serial shell am start -n com.vshower.prd_sr.instrumented/com.vshower.instrumented.InstrumentedActivity | Out-Null
Start-Sleep -Seconds 75

Write-Output "== walk to the stage map =="
& (Join-Path $PSScriptRoot 'walk-to-stage.ps1') -Serial $Serial | Out-Null
Save-Shot '01-map'

# The map layout shifts once the stage table populates, so probe for the node.
$candidates = @(@(490,1620),@(290,1640),@(700,1700),@(390,1840),@(690,1840),@(980,1840),@(540,1500),@(540,1100))
$entered = $false
foreach ($c in $candidates) {
    $before = Count-Hits 'GetTargetStageMonster'
    adb -s $Serial shell input tap $c[0] $c[1] | Out-Null
    Start-Sleep -Seconds 5
    if ((Count-Hits 'GetTargetStageMonster') -gt $before) {
        Write-Output "  node resolved at ($($c[0]),$($c[1]))"
        $entered = $true
        break
    }
}
if (-not $entered) { Write-Output "  no node resolved"; Save-Shot '02-nomatch'; exit 1 }

$stage = Last-Line 'game-values /reference/GetTargetStageMonster'
Write-Output "  $stage"
Save-Shot '03-battle-prep'

Write-Output "== begin battle =="
adb -s $Serial shell input tap 800 1825 | Out-Null
Start-Sleep -Seconds 25
Save-Shot '04-after-begin'

Write-Output "== result =="
Write-Output "  $(Last-Line 'game-values /mission/Start')"
Write-Output "  pid: $(adb -s $Serial shell pidof com.vshower.prd_sr.instrumented 2>&1)"
$asserts = Select-String -Path $log -Pattern 'ASSERTION Failed' | Select-Object -Last 3
foreach ($a in $asserts) { Write-Output "  $($a.Line.Trim())" }
