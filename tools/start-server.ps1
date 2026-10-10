# Blustone local replica server launcher.
#
#   . .\tools\start-server.ps1
#
# Starts server-ts in the background with the BlueStacks-compatible settings and
# the full 11-package CDN resource tree. Logs go to server-ts\logs\.

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$server = Join-Path $root 'server-ts'
$logs = Join-Path $server 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$env:BLUSTONE_BIND_HOST = '0.0.0.0'
$env:BLUSTONE_BASE_URL = 'http://10.0.2.2:8080'
$env:BLUSTONE_STATE_FILE = (Join-Path $server 'data\state.json')

# Defaults for a repeatable BlueStacks run. Set any of these BEFORE dot-sourcing
# this file to override; the script never clobbers a value you already chose.
# BLUSTONE_RESOURCE_VERSION is the CDN stamp the client is told to fetch. Bumping
# it forces the client to re-download every package, which is how the
# "all packages already current" bootstrap branch can be told apart from the
# "must download" branch when diagnosing a client stall.
if (-not $env:BLUSTONE_RESOURCE_VERSION) { $env:BLUSTONE_RESOURCE_VERSION = '1634663' }
if (-not $env:BLUSTONE_RESLIST_STAMP) { $env:BLUSTONE_RESLIST_STAMP = $env:BLUSTONE_RESOURCE_VERSION }
# Device profile used by the established battle/campaign runs. These flags
# must survive replica restarts; setting either to 0 deliberately disables it.
if (-not $env:BLUSTONE_SKIP_MISSION_TUTORIAL) { $env:BLUSTONE_SKIP_MISSION_TUTORIAL = '1' }
if (-not $env:BLUSTONE_SKIP_ALL_TUTORIALS) { $env:BLUSTONE_SKIP_ALL_TUTORIALS = '1' }
$env:BLUSTONE_PACKAGE_MODE = 'pkgi1-tree'
$env:BLUSTONE_PACKAGE_DIR = (Resolve-Path (Join-Path $root 'analysis\runtime-package-full')).Path
$env:BLUSTONE_PACKAGE_TREE_DIR = $env:BLUSTONE_PACKAGE_DIR
$env:BLUSTONE_PACKAGE_NAMES = 'E_NEW.jet,E_MIDAGE.jet,PK_LM2.jet,PK_LM4.jet,PK_LM5.jet,PK_MO3.jet,PK_MO5.jet,PK_MT3.jet,PK_MT5.jet,PK_WK1.jet,VD_MISSION.jet'
# Explicit research opt-in: deliver additional original JETs as separate PKGI
# packages rather than enlarging E_NEW. Preserve the established base ordering.
if ($env:BLUSTONE_PACKAGE_NAMES_EXTRA) {
    $extraPackageNames = @($env:BLUSTONE_PACKAGE_NAMES_EXTRA -split ',' |
        ForEach-Object { $_.Trim() } | Where-Object { $_ })
    foreach ($extraPackageName in $extraPackageNames) {
        if ($extraPackageName -notmatch '^[A-Za-z0-9_.-]+\.jet$') {
            throw "Invalid extra package basename: $extraPackageName"
        }
        if (($env:BLUSTONE_PACKAGE_NAMES -split ',') -notcontains $extraPackageName) {
            $env:BLUSTONE_PACKAGE_NAMES += ',' + $extraPackageName
        }
    }
}
# Assets folded into the E_NEW PKGI tree so the client unpacks them into
# files/local. Defaults only; set either before dot-sourcing to override.
#
# The real card art is in the recovered PAD pack:
#   recovered-assets\phone-2026-09-18\extracted\split_PADResource\assets
# which holds 570 C* packages (587 MB) - C001.jet, C001_Q.jet, C001A.jet,
# C001_EFT.jet, C001_SND.jet and so on, one family per card. A card's `_A*` and
# `_D*` animation slots live *inside* its C***.jet, so serving the family for
# the card the replica references removes the client's
# 'Cannot find the resource(_A0)' warnings and lets the village render in full
# art. Widen the list to serve more cards.
$padAssets = Join-Path $root 'recovered-assets\phone-2026-09-18\extracted\split_PADResource\assets'
if (-not $env:BLUSTONE_RESOURCE_ASSET_DIR) {
    if (Test-Path $padAssets) { $env:BLUSTONE_RESOURCE_ASSET_DIR = $padAssets }
    else { $env:BLUSTONE_RESOURCE_ASSET_DIR = (Resolve-Path (Join-Path $root 'analysis\extracted\assets')).Path }
}
if (-not $env:BLUSTONE_RESOURCE_ASSET_NAMES) {
    # BASE SET - unchanged from 2026-10-02. Every entry below is load-bearing:
    #
    #   MAP_ZONE_1.jet  the MISSION-MAP BACKDROP. `resource_id` on every area
    #                   record is this ART name (see FIXTURE_AREA_BACKDROP_ART in
    #                   server-ts/src/bootstrap.ts). It is the only MAP* pack in
    #                   the recovered corpus.
    #   ST001.jet       the STAGE/EPISODE art family. It is the stage `thumb`
    #                   namespace and it is MEASURED to miss as a map backdrop
    #                   ("[ERR] [RES] Can't find 'ST001' in ResMap." in 5/5 r015
    #                   legs), so it is kept only because `thumb` still names it.
    #   M001.jet        the monster family.
    #   MAIN_BG01/      village / main-screen art.
    #   MAIN_ICON.jet
    #   SNOW.jet        PROVEN WORKING: CreateArea (0xe91f0c) loads SR_SNOW at
    #                   0xe92490 and the client registers SR_SNOW01..03.
    #   UI_BATTLE.jet   battle HUD art.
    #   UI_BATTLE2.jet
    $stage = 'MAP_ZONE_1.jet,ST001.jet,M001.jet,MAIN_BG01.jet,MAIN_ICON.jet,SNOW.jet,UI_BATTLE.jet,UI_BATTLE2.jet'

    # OPT-IN EXTRA SET - empty by default. Widening the list forces the client
    # to re-download E_NEW, which has invalidated experiments before, so it is
    # never done implicitly. Candidates, all REAL files in the recovered pack,
    # for the stage-select popup that currently shows an empty panel:
    #   N001.jet N002.jet N003.jet   mission-node character sprites (N00x.jet
    #                                carries a plaintext atlas index: body, head,
    #                                r_arm, ... and a bare `N003` entry)
    #   N003_BG.jet                  that node's backdrop; the recovered layout
    #                                records name it explicitly -
    #                                KO/NEW/SR_MISSION/2_SR_UI_MS_ST/STAGE_POP
    #                                has <Animation res-name="N003_BG">, and
    #                                0_MS_ST_EX has N001_BG / N002_BG / N010_BG
    #                                (N002_BG and N010_BG are NOT in the pack).
    #   UI_MAIN.jet                  village/main UI art (9.3 MB).
    #   N001_BG.jet N008_BG.jet      the other two *_BG packs that exist.
    $extra = ''
    if ($env:BLUSTONE_RESOURCE_ASSET_NAMES_EXTRA) { $extra = $env:BLUSTONE_RESOURCE_ASSET_NAMES_EXTRA }
    $extra = ($extra -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ','

    # Card art, discovered rather than listed. The glob is a dial because the
    # published roster/source catalog uses C001..C006. Preserve an explicit
    # override; default to those six families, without loading the whole library.
    # Widen it with
    #   $env:BLUSTONE_CARD_ART_GLOB = 'C*.jet'
    # which is ~570 packages / 587 MB and therefore NOT the default.
    $cardGlob = $env:BLUSTONE_CARD_ART_GLOB
    if (-not $cardGlob) { $cardGlob = 'C001*.jet,C002*.jet,C003*.jet,C004*.jet,C005*.jet,C006*.jet' }
    # Glob the RESOLVED asset directory, not $padAssets: when the recovered PAD
    # pack is absent the fallback is the smaller APK copy, and a glob taken from
    # the other directory would name files the server then silently drops.
    $card = (@($cardGlob -split ',' | ForEach-Object {
        Get-ChildItem -LiteralPath $env:BLUSTONE_RESOURCE_ASSET_DIR -File -Filter $_.Trim() -ErrorAction SilentlyContinue
    }) | Sort-Object Name -Unique | ForEach-Object { $_.Name }) -join ','
    if (-not $card) {
        Write-Warning "BLUSTONE_CARD_ART_GLOB='$cardGlob' matched nothing under $($env:BLUSTONE_RESOURCE_ASSET_DIR); no card art will be folded into E_NEW."
    }

    $env:BLUSTONE_RESOURCE_ASSET_NAMES = (@($stage, $card, $extra) |
        Where-Object { $_ }) -join ','
}

# REFUSE TO START SILENTLY-SHORT. server.ts folds BLUSTONE_RESOURCE_ASSET_NAMES
# into the E_NEW PKGI tree and *skips any name that is not a readable file*
# (packageTreeEntries), so a typo or a pack that was never recovered produces a
# SHORTENED package with no error at all - which reads on device as "the art is
# missing" and sends the next agent hunting a client bug. Check the served set
# against the asset directory up front.
& {
    $missing = @()
    foreach ($packageName in ($env:BLUSTONE_PACKAGE_NAMES -split ',')) {
        if (-not (Test-Path -LiteralPath (Join-Path $env:BLUSTONE_PACKAGE_DIR $packageName) -PathType Leaf) -and
            -not (Test-Path -LiteralPath (Join-Path $env:BLUSTONE_RESOURCE_ASSET_DIR $packageName) -PathType Leaf)) {
            $missing += "package:$packageName"
        }
    }
    foreach ($name in ($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',')) {
        $n = $name.Trim()
        if (-not $n) { continue }
        $p = Join-Path $env:BLUSTONE_RESOURCE_ASSET_DIR $n
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { $missing += $n }
    }
    if ($missing.Count -gt 0) {
        throw ("BLUSTONE_RESOURCE_ASSET_NAMES names $($missing.Count) file(s) that do not exist under " +
            "$($env:BLUSTONE_RESOURCE_ASSET_DIR): $($missing -join ', '). server.ts drops missing names " +
            'silently, so this would ship a short package. Fix the name, or point ' +
            'BLUSTONE_RESOURCE_ASSET_DIR at the recovered pack.')
    }
}

# Diagnostic toggles are intentionally unset here. Set them before dot-sourcing
# if a bisect run needs them:
#   $env:BLUSTONE_DIAGNOSTIC_EMPTY_INVENTORY = '1'
#   $env:BLUSTONE_DIAGNOSTIC_RESPONSE_SPACING_MS = '500'

$stdout = Join-Path $logs 'server.stdout.log'
$stderr = Join-Path $logs 'server.stderr.log'

# Refuse to start on top of an already-listening replica. `npm run dev` spawns a
# child node process, so killing the recorded npm wrapper is NOT enough to free
# the port: the listener is a grandchild. Always stop via tools\stop-server.ps1,
# which kills the actual port owner.
$existing = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $owners = ($existing | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique) -join ', '
    throw "Port 8080 is already held by pid(s) $owners. Run tools\stop-server.ps1 first."
}

$proc = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', 'dev' `
    -WorkingDirectory $server -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr

$proc.Id | Set-Content (Join-Path $logs 'server.pid')
$ready = $false
$readyDeadline = [DateTime]::UtcNow.AddSeconds(40)
while ([DateTime]::UtcNow -lt $readyDeadline) {
    try {
        $probe = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/healthz' -UseBasicParsing -TimeoutSec 2
        $identity = $probe.Content | ConvertFrom-Json
        if ($probe.StatusCode -eq 200 -and $identity.ok -eq $true -and $identity.service -eq 'blustone-replica') {
            $ready = $true; break
        }
    } catch {
        $proc.Refresh()
        if ($proc.HasExited) { throw "Replica wrapper pid $($proc.Id) exited before readiness. Inspect $stderr." }
    }
    Start-Sleep -Milliseconds 500
}
if (-not $ready) {
    throw "Replica pid $($proc.Id) has not become ready within40s. Its handle is recorded; inspect that process/health rather than starting another."
}
Write-Output "server-ts started pid=$($proc.Id) -> http://10.0.2.2:8080 (docs: http://127.0.0.1:8080/docs)"
Write-Output "resource version=$($env:BLUSTONE_RESOURCE_VERSION) packages=$($env:BLUSTONE_PACKAGE_NAMES)"
Write-Output "asset dir=$($env:BLUSTONE_RESOURCE_ASSET_DIR)"
Write-Output ("assets (" + (@($env:BLUSTONE_RESOURCE_ASSET_NAMES -split ',' | Where-Object { $_.Trim() }).Count) +
    " folded into E_NEW): $($env:BLUSTONE_RESOURCE_ASSET_NAMES)")
# The two shipped profiles DISAGREE on purpose; keep it visible.
#   server-ts/.env.example  -> BLUSTONE_PACKAGE_NAMES = E_NEW,E_MIDAGE,UI_XML_RO.db
#                              the RECONSTRUCTED-RESOURCES smoke profile. It needs
#                              analysis/reconstructed-resources, and it serves no
#                              stage art at all, so the expedition map draws
#                              nothing on it.
#   tools/start-server.ps1 -> 11 packages + the asset set above. This is the
#                              BlueStacks/device profile and the only one that has
#                              ever run the game.
# Do not copy the .env.example list into a device run.
Write-Output "NOTE: .env.example advertises 3 packages against a different package dir; this file is the 11-package device profile. See server-ts/README.md."
