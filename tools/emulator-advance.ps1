param(
    [string]$Serial = "emulator-5554",
    [switch]$ResetApp,
    [switch]$RunGuestFlow
)

$ErrorActionPreference = "Stop"
if ($Serial -notmatch '^emulator-') {
    throw "Refusing to modify non-emulator serial '$Serial'. The physical phone is read-only."
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$uiRoot = (Resolve-Path (Join-Path $root "analysis\reconstructed-resources\UI_XML_RO.db")).Path
$capture = Join-Path $root "analysis\capture\emulator-instrumentation.log"

function Invoke-Adb {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & adb @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "adb failed ($LASTEXITCODE): $($Arguments -join ' ')"
    }
}

function Wait-For {
    param([Parameter(Mandatory)][scriptblock]$Check, [int]$TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Check) { return }
        Start-Sleep -Seconds 2
    }
    throw "Timed out after $TimeoutSeconds seconds."
}

Invoke-Adb @("-s", $Serial, "wait-for-device")
if ((adb -s $Serial shell getprop sys.boot_completed).Trim() -ne "1") {
    Wait-For { (adb -s $Serial shell getprop sys.boot_completed 2>$null).Trim() -eq "1" } 120
}
Invoke-Adb @("-s", $Serial, "logcat", "-c")

if ($ResetApp) {
    Invoke-Adb @("-s", $Serial, "shell", "am", "force-stop", "com.vshower.prd_sr")
    Invoke-Adb @("-s", $Serial, "shell", "pm", "clear", "com.vshower.prd_sr")
}

Invoke-Adb @("-s", $Serial, "shell", "am", "start", "-n", "com.vshower.prd_sr/com.vshower.sr.MainActivity")
Wait-For { (adb -s $Serial shell run-as com.vshower.prd_sr ls files/local/UI_XML_RO.db/000005.ldb 2>$null) -ne $null } 120

# The native downloader cannot safely replace the open base SSTable. Install
# the generated uncompressed delta while the app is stopped, then reopen it.
Invoke-Adb @("-s", $Serial, "shell", "am", "force-stop", "com.vshower.prd_sr")
$currentName = (Get-Content (Join-Path $uiRoot "CURRENT") -Raw).Trim()
$manifestPath = Join-Path $uiRoot $currentName
$delta = Get-ChildItem $uiRoot -Filter "*.ldb" | Where-Object Name -ne "000005.ldb" | Select-Object -First 1
if (-not $delta) { throw "No reconstructed UI delta SSTable found in $uiRoot" }

$stage = "/data/local/tmp/blustone-ui-delta"
Invoke-Adb @("-s", $Serial, "shell", "rm", "-rf", $stage)
Invoke-Adb @("-s", $Serial, "shell", "mkdir", $stage)
Invoke-Adb @("-s", $Serial, "push", $delta.FullName, "$stage/000016.ldb")
Invoke-Adb @("-s", $Serial, "push", (Join-Path $uiRoot "CURRENT"), "$stage/CURRENT")
Invoke-Adb @("-s", $Serial, "push", $manifestPath, "$stage/MANIFEST")
Invoke-Adb @("-s", $Serial, "shell", "run-as", "com.vshower.prd_sr", "cp", "$stage/000016.ldb", "files/local/UI_XML_RO.db/000016.ldb")
Invoke-Adb @("-s", $Serial, "shell", "run-as", "com.vshower.prd_sr", "cp", "$stage/CURRENT", "files/local/UI_XML_RO.db/CURRENT")
Invoke-Adb @("-s", $Serial, "shell", "run-as", "com.vshower.prd_sr", "cp", "$stage/MANIFEST", "files/local/UI_XML_RO.db/$currentName")
Invoke-Adb @("-s", $Serial, "shell", "am", "start", "-n", "com.vshower.prd_sr/com.vshower.sr.MainActivity")

if ($RunGuestFlow) {
    Start-Sleep -Seconds 8
    Invoke-Adb @("-s", $Serial, "shell", "input", "tap", "540", "1770")
    Start-Sleep -Seconds 8
    Invoke-Adb @("-s", $Serial, "shell", "input", "tap", "540", "1500")
    Start-Sleep -Seconds 15
}

$log = adb -s $Serial logcat -d -v threadtime
$log | Set-Content -LiteralPath $capture -Encoding utf8
Write-Output "instrumentation_log=$capture"
Write-Output "ui_delta=$($delta.Name)"
Write-Output "missing_key_lines=$(@($log | Select-String 'Getting EN/|FindTextUI Text Miss|PV_UNKNOWN').Count)"
Write-Output "native_failure_lines=$(@($log | Select-String 'BuildColor|Assertion|FATAL|SIGSEGV|Corruption').Count)"
