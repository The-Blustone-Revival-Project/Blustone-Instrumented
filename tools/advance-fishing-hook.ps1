# Finite original-tutorial gameplay, guarded by read-only native phase snapshots.
param([ValidateRange(1,8)][int]$MaxBursts=8,[ValidateSet(0,1)][int]$ExpectedPhase=0)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
Set-Location $root
$adb=Join-Path $root 'tools/android-sdk/platform-tools/adb.exe'
$java=Join-Path $root 'tools/jdk/jdk-21.0.12.1+1/bin/java.exe'
$evidence=Join-Path $root 'analysis/testing/fishing-004'
$clientPid=(& $adb -s 127.0.0.1:5555 shell pidof com.vshower.prd_sr.instrumented).Trim()
if($clientPid -notmatch '^\d+$'){throw 'No single instrumented client process'}
& $adb -s 127.0.0.1:5555 forward tcp:8701 "jdwp:$clientPid" | Out-Null
for($burst=1;$burst -le $MaxBursts;$burst++) {
  $foreground=& $adb -s 127.0.0.1:5555 shell dumpsys activity activities | Select-String 'mResumedActivity'
  if($foreground -notmatch 'com.vshower.prd_sr.instrumented/com.vshower.instrumented.InstrumentedActivity'){throw 'Wrong foreground'}
  $out=Join-Path $evidence "guarded-phase$ExpectedPhase-$burst.txt"
  $err=Join-Path $evidence "guarded-phase$ExpectedPhase-$burst.stderr"
  $observer=Start-Process -FilePath $java -ArgumentList '-cp','analysis/input-probe','InspectNativeInput','8701','--fishing-hook' -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
  # One ordinary hook tap supplies the diagnostic breakpoint; reader writes no memory.
  Start-Sleep -Milliseconds 1200
  & $adb -s 127.0.0.1:5555 shell input tap 550 800
  if(-not $observer.WaitForExit(10000)){throw 'Observer still running; stop inputs and inspect its handle'}
  if($observer.ExitCode -ne 0){throw "Phase snapshot rejected: $(Get-Content $err -Raw)"}
  $phase=Get-Content $out -Raw
  Write-Output $phase.Trim()
  if($phase -notmatch "mode65c=0 .*phase7c8=$ExpectedPhase input7c9=1"){Write-Output 'Stopped at phase/input change';break}
  if($phase -notmatch 'gauge658=([0-9.]+)'){throw 'Missing gauge'}
  $gauge=[double]::Parse($Matches[1],[Globalization.CultureInfo]::InvariantCulture)
  $threshold=if($ExpectedPhase -eq 0){70}else{100}
  if($gauge -ge $threshold){Write-Output 'Stopped at phase threshold';break}
  & $adb -s 127.0.0.1:5555 shell 'CLASSPATH=/mnt/windows/BstSharedFolder/RapidTouch.jar app_process /system/bin RapidTouch 12 120' | Select-Object -Last 1
}
