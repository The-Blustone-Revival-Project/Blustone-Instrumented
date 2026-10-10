# Root only: start after a fresh visual check of the expected active battle HUD.
param(
  [Parameter(Mandatory=$true)][ValidatePattern('^CB[0-9]{4}$')][string]$CombatId,
  [ValidateRange(1,100)][int]$MaxBursts=20,
  [switch]$BeginBattle,
  [switch]$ObserveMaterials,
  [Parameter(Mandatory=$true)][string]$EvidenceDir
)
$ErrorActionPreference='Stop'
$attackRoot=Split-Path $PSScriptRoot -Parent
$attackAdb=Join-Path $PSScriptRoot 'android-sdk/platform-tools/adb.exe'
$attackJava=Join-Path $PSScriptRoot 'jdk/jdk-21.0.12.1+1/bin/java.exe'
$attackClasses=Join-Path $attackRoot 'analysis/input-probe'
$attackSerial='127.0.0.1:5555'
$attackDir=[IO.Path]::GetFullPath($EvidenceDir)
$attackEvidenceRoot=[IO.Path]::GetFullPath((Join-Path $attackRoot 'analysis/testing'))+[IO.Path]::DirectorySeparatorChar
if(-not $attackDir.StartsWith($attackEvidenceRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Evidence must be under analysis/testing'}
New-Item -ItemType Directory -Path $attackDir -Force | Out-Null
$attackPid=([string](& $attackAdb -s $attackSerial shell pidof com.vshower.prd_sr.instrumented)).Trim()
if($LASTEXITCODE -ne 0 -or $attackPid -notmatch '^\d+$'){throw 'Exactly one instrumented client required'}
& $attackAdb -s $attackSerial forward tcp:8701 "jdwp:$attackPid" | Out-Null
if($LASTEXITCODE -ne 0){throw 'JDWP forward failed'}
if($BeginBattle){
  # Explicit opt-in only after root visually verifies the expected preparation
  # screen. Then native owner/start/input guards control the entire fight.
  $attackForeground=(& $attackAdb -s $attackSerial shell dumpsys activity activities) -join "`n"
  if($LASTEXITCODE -ne 0 -or $attackForeground -notmatch '(?s)mResumedActivity: ActivityRecord\{[^}]*com\.vshower\.prd_sr\.instrumented/com\.vshower\.instrumented\.InstrumentedActivity'){throw 'Instrumented activity is not resumed; no Begin input'}
  & $attackAdb -s $attackSerial shell input tap 540 1820 | Out-Null
  if($LASTEXITCODE -ne 0){throw 'Begin input failed'}
  Start-Sleep -Milliseconds 2500
}
$attackAccepted=0
for($attackIndex=1;$attackIndex -le $MaxBursts;$attackIndex++){
  $attackForeground=(& $attackAdb -s $attackSerial shell dumpsys activity activities) -join "`n"
  if($LASTEXITCODE -ne 0 -or $attackForeground -notmatch '(?s)mResumedActivity: ActivityRecord\{[^}]*com\.vshower\.prd_sr\.instrumented/com\.vshower\.instrumented\.InstrumentedActivity'){throw 'Instrumented activity is not resumed; stop inputs'}
  $attackTag='{0:D3}' -f $attackIndex
  $attackOut=Join-Path $attackDir "$attackTag.stdout.txt"
  $attackErr=Join-Path $attackDir "$attackTag.stderr.txt"
  if((Test-Path -LiteralPath $attackOut) -or (Test-Path -LiteralPath $attackErr)){throw 'Use a fresh evidence directory'}
  $attackObserverMode=if($ObserveMaterials){'--episode-materials'}else{'--episode-scene'}
  $attackProcess=Start-Process -FilePath $attackJava -ArgumentList '-cp',('"'+$attackClasses+'"'),'InspectNativeInput','8701',$attackObserverMode,'--frame' -WindowStyle Hidden -RedirectStandardOutput $attackOut -RedirectStandardError $attackErr -PassThru
  $attackReady=$false
  $attackDeadline=[DateTime]::UtcNow.AddSeconds(3)
  while(-not $attackProcess.HasExited -and [DateTime]::UtcNow -lt $attackDeadline){
    if((Test-Path -LiteralPath $attackOut) -and ((Get-Content -LiteralPath $attackOut -Raw) -match 'Waiting up to30s')){$attackReady=$true;break}
    Start-Sleep -Milliseconds 20
  }
  if(-not $attackReady -and $attackProcess.HasExited -and (Test-Path -LiteralPath $attackOut)){
    $attackReady=(Get-Content -LiteralPath $attackOut -Raw) -match 'Waiting up to30s'
  }
  if(-not $attackReady){throw "Observer not ready; stop inputs, process $($attackProcess.Id) retained"}
  # The original renderer supplies the breakpoint without a diagnostic touch.
  if(-not $attackProcess.WaitForExit(6000)){throw "Observer still running; stop inputs, process $($attackProcess.Id) retained"}
  $attackText=Get-Content -LiteralPath $attackOut -Raw
  $attackErrorText=Get-Content -LiteralPath $attackErr -Raw
  if($attackProcess.ExitCode -ne 0 -or $attackErrorText){Write-Output $attackText;throw 'Observer rejected state; no burst'}
  Write-Output $attackText.Trim()
  $attackMatch=[regex]::Match($attackText,'selectedCombatId=(\w+) leftRemain2e4=(-?\d+) rightRemain2e8=(-?\d+) pause140=([0-9a-f]+) terminal=(\S+)')
  if(-not $attackMatch.Success -or $attackMatch.Groups[1].Value -ne $CombatId){throw 'Combat identity mismatch; no burst'}
  if([int]$attackMatch.Groups[2].Value -eq 0 -or [int]$attackMatch.Groups[3].Value -eq 0){Write-Output "Stopped at terminal state; bursts=$attackAccepted";break}
  if($attackText -notmatch 'Episode modalPrimary=0 modalSecondary=0 topELFvptr=0'){Write-Output "Stopped at modal/unavailable modal state; bursts=$attackAccepted";break}
  if($attackMatch.Groups[4].Value -ne '0' -or $attackText -notmatch 'Episode armed=yes '){
    Write-Output "Waiting without input for armed state; bursts=$attackAccepted iteration=$attackIndex"
    Start-Sleep -Milliseconds 100
    continue
  }
  & $attackAdb -s $attackSerial shell 'CLASSPATH=/mnt/windows/BstSharedFolder/RapidTouch.jar app_process /system/bin RapidTouch 12 50 695 900' | Set-Content -LiteralPath (Join-Path $attackDir "$attackTag.taps.txt")
  if($LASTEXITCODE -ne 0){throw 'Burst rejected; stop inputs'}
  $attackAccepted++
}
Write-Output "Bounded Episode input finished; bursts=$attackAccepted limit=$MaxBursts"
