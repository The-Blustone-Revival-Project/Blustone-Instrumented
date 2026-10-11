# Root-only fallback after a fresh visual check of the expected preparation/HUD.
# No JDWP. Pixel signatures do not establish native combat ID/pause/armed state.
param(
 # Legacy parameter name retained. Arena and one ordinary campaign replay
 # are allowlisted beside Episode IDs; caller must verify native preparation.
 [Parameter(Mandatory=$true)][ValidatePattern('^(CB[0-9]{4}|b_00_01|n_01_01)$')][string]$ExpectedCombatId,
 [Parameter(Mandatory=$true)][ValidateRange(1,5)][int]$ExpectedEnemyCount,
 [Parameter(Mandatory=$true)][ValidatePattern('^\d+$')][string]$ExpectedClientPid,
 [Parameter(Mandatory=$true)][string]$EvidenceDir,
 [ValidateRange(1,300)][int]$MaxBursts=150,
 [ValidateRange(0,12)][int]$InitialHudWaitFrames=0,
 [string]$SkillPlanFile,
 [string]$ExchangePlanFile,
 [switch]$PauseAfterExchange,
 [switch]$PauseAfterSkill,
 [switch]$CleanupMoveAfterExchange,
 [ValidateRange(0,299)][int]$PauseAfterBursts=0,
 [switch]$BeginBattle,
 [switch]$ResumeBattle
)
$ErrorActionPreference='Stop'
$visualRoot=Split-Path $PSScriptRoot -Parent
$visualAdb=Join-Path $visualRoot 'local/toolchains/android-sdk/platform-tools/adb.exe'
$visualPython=Join-Path $visualRoot 'local/toolchains/python-venv/Scripts/python.exe'
$visualGuard=Join-Path $PSScriptRoot 'battle-hud-guard.py'
if($ExpectedCombatId -eq 'n_01_01'){$visualGuard=Join-Path $PSScriptRoot 'campaign-hud-guard.py'}
$visualSkillGuard=Join-Path $PSScriptRoot 'battle-skill-button-guard.py'
$visualDir=[IO.Path]::GetFullPath($EvidenceDir)
$visualAllowed=[IO.Path]::GetFullPath((Join-Path $visualRoot 'local/captures/testing'))+[IO.Path]::DirectorySeparatorChar
if(-not $visualDir.StartsWith($visualAllowed,[StringComparison]::OrdinalIgnoreCase)){throw 'Evidence must stay under local/captures/testing'}
if(Test-Path -LiteralPath $visualDir){throw 'Use a fresh evidence directory'}
if($PauseAfterBursts -ge $MaxBursts){throw 'Pause milestone must precede the burst limit'}
if($BeginBattle -and $ResumeBattle){throw 'Begin and Resume are mutually exclusive'}
if($ExpectedCombatId -in @('b_00_01','n_01_01') -and ($SkillPlanFile -or $ExchangePlanFile)){
 throw 'Arena/campaign replay support ordinary attack/pause only; skill/exchange geometry is not validated'
}
if($ExpectedCombatId -eq 'n_01_01' -and $ExpectedEnemyCount -ne 1){throw 'Known campaign replay requires exactly one expected enemy'}
if($SkillPlanFile -and $ExchangePlanFile){throw 'Use separate observed runs for skill and exchange plans'}
if($PauseAfterSkill -and (-not $SkillPlanFile -or $PauseAfterBursts -gt 0)){throw 'PauseAfterSkill requires one skill plan and no burst pause'}
if($PauseAfterExchange -and -not $ExchangePlanFile){throw 'PauseAfterExchange requires one exchange plan'}
if($CleanupMoveAfterExchange -and (-not $ExchangePlanFile -or -not $PauseAfterExchange)){throw 'CleanupMoveAfterExchange requires an exchange plan and post-exchange pause'}
$visualExchangePlan=$null
if($ExchangePlanFile){
 $plans=@(Get-Content -LiteralPath $ExchangePlanFile -Raw|ConvertFrom-Json)
 if($plans.Count -ne 1){throw 'Exactly one explicit exchange attempt per run'}
 $visualExchangePlan=$plans[0]
 foreach($field in @('after_bursts','start_x','start_y','end_x','end_y','duration_ms')){
  if($visualExchangePlan.$field -isnot [long] -and $visualExchangePlan.$field -isnot [int]){throw 'Exchange fields must be scalar integers'}
 }
 if($visualExchangePlan.after_bursts -lt 0 -or $visualExchangePlan.after_bursts -ge $MaxBursts){throw 'Exchange milestone outside burst limit'}
 if($visualExchangePlan.start_x -lt 850 -or $visualExchangePlan.start_x -gt 1040 -or
    $visualExchangePlan.start_y -lt 1550 -or $visualExchangePlan.start_y -gt 1800){throw 'Exchange capture must be caller-reviewed right-rear body point'}
 if($visualExchangePlan.end_x -lt 470 -or $visualExchangePlan.end_x -gt 610 -or
    $visualExchangePlan.end_y -lt 1000 -or $visualExchangePlan.end_y -gt 1250){throw 'Exchange drop must stay in caller-reviewed upper IN region, away from door icon'}
 if($visualExchangePlan.duration_ms -lt 2000 -or $visualExchangePlan.duration_ms -gt 2600){throw 'Exchange duration must be bounded2000..2600ms'}
}
$visualSkillPlan=@()
if($SkillPlanFile){
 $visualSkillPlan=@(Get-Content -LiteralPath $SkillPlanFile -Raw|ConvertFrom-Json)
 if($visualSkillPlan.Count -gt 4){throw 'At most four explicit skill attempts per run'}
 if($PauseAfterSkill -and $visualSkillPlan.Count -ne 1){throw 'PauseAfterSkill requires exactly one skill attempt'}
 $visualMilestones=@()
 foreach($attempt in $visualSkillPlan){
  if($attempt.after_bursts -isnot [long] -and $attempt.after_bursts -isnot [int]){throw 'Skill milestone must be an integer'}
  if(($attempt.x -isnot [long] -and $attempt.x -isnot [int]) -or ($attempt.y -isnot [long] -and $attempt.y -isnot [int])){throw 'Skill coordinates must be scalar integers'}
  if($attempt.after_bursts -lt 0 -or $attempt.after_bursts -ge $MaxBursts -or $attempt.after_bursts -in $visualMilestones){throw 'Skill milestones must be unique and inside the burst limit'}
  if($attempt.PSObject.Properties.Name -contains 'require_visible_button'){
   if($attempt.require_visible_button -isnot [bool]){throw 'require_visible_button must be Boolean'}
   if($attempt.require_visible_button){
    if($attempt.expected_cost -isnot [long] -and $attempt.expected_cost -isnot [int]){throw 'Visible skill guard requires integer expected_cost'}
    if($attempt.expected_cost -notin @(3,4)){throw 'Visible skill guard supports observed cost3/4 only'}
    if(($attempt.max_defer_bursts -isnot [long] -and $attempt.max_defer_bursts -isnot [int]) -or $attempt.max_defer_bursts -lt 0 -or $attempt.max_defer_bursts -gt 3){throw 'Visible skill defer window must be integer0..3'}
    if(-not(Test-Path -LiteralPath $visualSkillGuard)){throw 'Visible skill guard tool missing'}
   }
  }
  if(-not $attempt.require_visible_button -and ($attempt.PSObject.Properties.Name -contains 'expected_cost' -or $attempt.PSObject.Properties.Name -contains 'max_defer_bursts')){throw 'Visible guard fields require require_visible_button=true'}
  if($attempt.PSObject.Properties.Name -contains 'hold_ms'){
   if(-not $attempt.require_visible_button -or ($attempt.hold_ms -isnot [long] -and $attempt.hold_ms -isnot [int]) -or $attempt.hold_ms -lt 50 -or $attempt.hold_ms -gt 250){throw 'hold_ms requires a visible guard and integer50..250'}
  }
  if(-not(($attempt.x -in @(300,450) -and $attempt.y -eq 535) -or ($attempt.x -eq 345 -and $attempt.y -eq 1385) -or
    ($attempt.x -ge 250 -and $attempt.x -le 390 -and $attempt.y -ge 1300 -and $attempt.y -le 1550) -or
    ($attempt.x -ge 800 -and $attempt.x -le 1050 -and $attempt.y -ge 1200 -and $attempt.y -le 1550))){throw 'Only caller-reviewed front/support or bounded rear skill points are supported'}
  $visualMilestones+=$attempt.after_bursts
 }
 $visualSkillPlan=@($visualSkillPlan|Sort-Object after_bursts)
 for($planIndex=1;$planIndex -lt $visualSkillPlan.Count;$planIndex++){
  if($visualSkillPlan[$planIndex].after_bursts-$visualSkillPlan[$planIndex-1].after_bursts -lt 4){throw 'Space skill attempts by at least four ordinary bursts'}
 }
}
New-Item -ItemType Directory -Path $visualDir|Out-Null
if($SkillPlanFile){$visualSkillPlan|ConvertTo-Json|Set-Content (Join-Path $visualDir 'skill-plan.json')}
if($visualExchangePlan){$visualExchangePlan|ConvertTo-Json|Set-Content (Join-Path $visualDir 'exchange-plan.json')}
$visualPending=@()
$visualHudLayout=if($ExpectedCombatId -eq 'b_00_01'){'arena'}elseif($ExpectedCombatId -eq 'n_01_01'){'campaign'}else{'standard'}
function Retain-VisualHelper($process,[string]$operation,$stdoutTask=$null,$stderrTask=$null,$file=$null) {
 # Retain the object/streams while this shell lives, and durable identity for
 # root to inspect after a thrown timeout. No new input or app restart follows.
 $script:visualPending+=@{Process=$process;Stdout=$stdoutTask;Stderr=$stderrTask;File=$file}
 [pscustomobject]@{pid=$process.Id;operation=$operation;started_utc=$process.StartTime.ToUniversalTime().ToString('o');expected_client_pid=$ExpectedClientPid;status='live_at_observation_timeout'}|
  ConvertTo-Json|Set-Content (Join-Path $visualDir 'pending-helper.json')
 throw "Observation timed out during $operation; stop inputs, live helper PID $($process.Id) retained. Inspect that handle before another controller."
}
function Invoke-VisualTextProcess([string]$executable,[string[]]$arguments,[string]$operation) {
 $start=[Diagnostics.ProcessStartInfo]::new()
 $start.FileName=$executable;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
 $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 foreach($arg in $arguments){$start.ArgumentList.Add($arg)}
 $process=[Diagnostics.Process]::Start($start)
 $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
 try {
  if(-not $process.WaitForExit(5000)){Retain-VisualHelper $process $operation $stdout $stderr}
  if(-not $stdout.Wait(1000) -or -not $stderr.Wait(1000)){throw "Helper $($process.Id) exited but streams incomplete during $operation; stop inputs"}
  if($process.ExitCode -ne 0){throw "$operation failed; stop inputs: $($stderr.Result)"}
  if($stderr.Result){throw "$operation returned diagnostics; stop inputs: $($stderr.Result)"}
  return $stdout.Result
 } finally {if($process.HasExited){$process.Dispose()}}
}
function Invoke-VisualAdb([string[]]$arguments,[string]$operation) {
 Invoke-VisualTextProcess $visualAdb (@('-s','127.0.0.1:5555')+$arguments) $operation
}
function Confirm-VisualForeground {
 $current=(Invoke-VisualAdb @('shell','pidof','com.vshower.prd_sr.instrumented') 'pidof').Trim()
 if($current -ne $ExpectedClientPid){throw 'Client identity changed; stop inputs'}
 $foreground=Invoke-VisualAdb @('shell','dumpsys','activity','activities') 'foreground inspection'
 if($foreground -notmatch 'mResumedActivity: ActivityRecord\{[^}]*com\.vshower\.prd_sr\.instrumented/com\.vshower\.instrumented\.InstrumentedActivity'){throw 'Instrumented activity not resumed; stop inputs'}
}
function Capture-VisualFrame([string]$path) {
 $start=[Diagnostics.ProcessStartInfo]::new()
 $start.FileName=$visualAdb;$start.UseShellExecute=$false;$start.CreateNoWindow=$true;$start.RedirectStandardOutput=$true
 foreach($arg in @('-s','127.0.0.1:5555','exec-out','screencap','-p')){$start.ArgumentList.Add($arg)}
 $capture=[Diagnostics.Process]::Start($start)
 $file=[IO.File]::Create($path)
 try {
  $copy=$capture.StandardOutput.BaseStream.CopyToAsync($file)
  if(-not $copy.Wait(5000)){Retain-VisualHelper $capture 'screencap stream' $copy $null $file}
  if(-not $capture.WaitForExit(1000)){Retain-VisualHelper $capture 'screencap exit' $copy $null $file}
  if($capture.ExitCode -ne 0){throw 'Screencap failed; inputs stopped'}
 } finally {if($capture.HasExited){$file.Dispose();$capture.Dispose()}}
}
Confirm-VisualForeground
Write-Output "Visual fallback expected=$ExpectedCombatId enemies=$ExpectedEnemyCount client=$ExpectedClientPid; encounter/roster were verified by caller, not by pixels."
if($BeginBattle){
 # Ordinary preparation has separate Dispatch and Begin buttons. Use its
 # caller-verified right Begin button; the center point is the gap there.
 $visualBeginX=if($ExpectedCombatId -eq 'n_01_01'){'800'}else{'540'}
 Invoke-VisualAdb @('shell','input','tap',$visualBeginX,'1820') 'Begin input'|Out-Null
}
if($ResumeBattle){
 # Explicit opt-in only after caller verifies the normal Paused screen.
 Invoke-VisualAdb @('shell','input','tap','540','875') 'Resume input'|Out-Null
}
$accepted=0;$loading=0;$unconfirmed=0;$skillAttempt=0;$skillInputs=0;$skillSkipped=0;$exchangeAttempt=0
for($iteration=1;$iteration -le ($MaxBursts*8+15);$iteration++){
 Confirm-VisualForeground
 $tag='{0:D3}'-f $iteration
 $shot=Join-Path $visualDir "$tag.png"
 Capture-VisualFrame $shot
 $raw=Invoke-VisualTextProcess $visualPython @($visualGuard,$shot,[string]$ExpectedEnemyCount,$visualHudLayout) 'pixel guard'
 $raw|Set-Content (Join-Path $visualDir "$tag.guard.json")
 $gate=$raw|ConvertFrom-Json
 if(-not $gate.battle_hud){
  $initialWait=if($BeginBattle -or $ResumeBattle){12}else{$InitialHudWaitFrames}
  if($accepted -eq 0 -and $gate.reason -eq 'hud_not_confirmed' -and $loading -lt $initialWait){$loading++;Start-Sleep -Milliseconds 200;continue}
  # Skill cut-ins temporarily cover the HUD. Observe without touching and
  # resume only when a fresh frame passes every gate. Results/menus receive
  # no inputs, and all-enemy defeat crosses still stop immediately.
  if($accepted -gt 0 -and $gate.reason -eq 'hud_not_confirmed' -and $unconfirmed -lt 6){$unconfirmed++;Start-Sleep -Milliseconds 200;continue}
  Write-Output "Stopped at unconfirmed HUD; bursts=$accepted frame=$tag (not an outcome claim).";break
 }
 $unconfirmed=0
 if($PauseAfterBursts -gt 0 -and $accepted -ge $PauseAfterBursts){
  # Explicit diagnostic pause only after a fresh confirmed active HUD. This
  # is normal Android Back input, not a native pause/state write or outcome.
  Invoke-VisualAdb @('shell','input','keyevent','4') 'requested diagnostic pause'|
   Set-Content (Join-Path $visualDir "$tag.pause-input.txt")
  Write-Output "Requested diagnostic pause after $accepted bursts; verify the resulting UI before observation/resume."
  break
 }
 if($visualExchangePlan -and $exchangeAttempt -eq 0 -and $accepted -ge $visualExchangePlan.after_bursts){
  # One ordinary same-contact Android swipe. This does not force capture,
  # opening, cooldown, exchange or cleanup; caller measures those separately.
  $p=$visualExchangePlan
  Invoke-VisualAdb @('shell','input','swipe',[string]$p.start_x,[string]$p.start_y,[string]$p.end_x,[string]$p.end_y,[string]$p.duration_ms) 'single planned exchange gesture'|
   Set-Content (Join-Path $visualDir "$tag.exchange-input.txt")
  [pscustomobject]@{after_bursts=$accepted;start_x=$p.start_x;start_y=$p.start_y;end_x=$p.end_x;end_y=$p.end_y;duration_ms=$p.duration_ms;status='attempt_only_native_exchange_and_cleanup_unproved'}|
   ConvertTo-Json|Set-Content (Join-Path $visualDir "$tag.exchange-attempt.json")
  $exchangeAttempt++
  if($CleanupMoveAfterExchange){
   # Source-normal follow-up movement, away from IN/OUT. A caught front actor
   # (IsWaiting=false) is cleared by OnProcessMove before its pointer-ID test.
   # This is an attempt, not a forced reset; verify the caught pair afterward.
   Invoke-VisualAdb @('shell','input','swipe','695','900','1000','500','300') 'planned post-exchange cleanup movement'|
    Set-Content (Join-Path $visualDir "$tag.exchange-cleanup-input.txt")
  }
  if($PauseAfterExchange){
   Invoke-VisualAdb @('shell','input','keyevent','4') 'requested post-exchange diagnostic pause'|
    Set-Content (Join-Path $visualDir "$tag.exchange-pause-input.txt")
   Write-Output 'Requested normal pause after exchange attempt; verify resulting scene and native catch cleanup before ordinary attacks.'
   break
  }
  continue
 }
 if($skillAttempt -lt $visualSkillPlan.Count -and $accepted -ge $visualSkillPlan[$skillAttempt].after_bursts){
  $attempt=$visualSkillPlan[$skillAttempt]
  $visualAttemptAllowed=$true
  if($attempt.require_visible_button){
   if($accepted -gt ($attempt.after_bursts+$attempt.max_defer_bursts)){
    [pscustomobject]@{after_bursts=$accepted;x=$attempt.x;y=$attempt.y;status='skipped_visible_button_window_expired'}|
     ConvertTo-Json|Set-Content (Join-Path $visualDir "$tag.skill-skipped.json")
    $skillAttempt++;$skillSkipped++;$visualAttemptAllowed=$false
    if($PauseAfterSkill){
     Invoke-VisualAdb @('shell','input','keyevent','4') 'requested pause after expired skill window'|
      Set-Content (Join-Path $visualDir "$tag.skill-window-pause-input.txt")
     Write-Output 'Requested normal pause after skill window expired; no skill input was sent.';break
    }
   } else {
    $skillRaw=Invoke-VisualTextProcess $visualPython @($visualSkillGuard,$shot,[string]$attempt.x,[string]$attempt.y,[string]$attempt.expected_cost,[string]$ExpectedEnemyCount) 'visible skill button inspection'
    $skillRaw|Set-Content (Join-Path $visualDir "$tag.skill-guard.json")
    $skillGate=$skillRaw|ConvertFrom-Json
    $visualAttemptAllowed=$skillGate.visible_button -eq $true
   }
  }
  if($visualAttemptAllowed){
  # One normal button attempt, NOT an eligibility/opacity/cost assertion.
  # Native checks may refuse it or the moving icon may be missed. Never force
  # Rage/actor state. Fresh HUD is required before any following input.
  if($attempt.hold_ms){
   # Same-point ordinary Android contact, no actor drag or native state write.
   Invoke-VisualAdb @('shell','input','swipe',[string]$attempt.x,[string]$attempt.y,[string]$attempt.x,[string]$attempt.y,[string]$attempt.hold_ms) 'single held skill attempt'|
    Set-Content (Join-Path $visualDir "$tag.skill-tap.txt")
  } else {
   Invoke-VisualAdb @('shell','input','tap',[string]$attempt.x,[string]$attempt.y) 'single planned skill attempt'|
    Set-Content (Join-Path $visualDir "$tag.skill-tap.txt")
  }
  [pscustomobject]@{after_bursts=$accepted;x=$attempt.x;y=$attempt.y;hold_ms=$attempt.hold_ms;status='attempt_only_native_acceptance_unproved'}|
   ConvertTo-Json|Set-Content (Join-Path $visualDir "$tag.skill-attempt.json")
  $skillAttempt++;$skillInputs++
  if($PauseAfterSkill){
   Invoke-VisualAdb @('shell','input','keyevent','4') 'requested post-skill diagnostic pause'|
    Set-Content (Join-Path $visualDir "$tag.skill-pause-input.txt")
   Write-Output 'Requested normal pause after skill attempt; verify resulting UI before observation/resume.'
   break
  }
  continue
  }
  # Deferred/expired attempts fall through to ordinary fighting below. Do not
  # idle the active scene while waiting for a skill button or another milestone.
 }
 Invoke-VisualAdb @('shell','CLASSPATH=/mnt/windows/BstSharedFolder/RapidTouch.jar app_process /system/bin RapidTouch 12 50 695 900') 'bounded touch burst'|Set-Content (Join-Path $visualDir "$tag.taps.txt")
 $accepted++
 if($accepted -ge $MaxBursts){Write-Output "Burst bound reached: $accepted; re-observe before continuing.";break}
}
Write-Output "Visual fallback completed; bursts=$accepted skillAttempts=$skillInputs skippedSkillWindows=$skillSkipped exchangeAttempts=$exchangeAttempt. No native outcome, skill or exchange acceptance was inferred."
