# Stop the local Blustone replica server, reliably.
#
#   .\tools\stop-server.ps1
#
# `npm run dev` starts npm -> node -> tsx -> node, so the process recorded in
# server-ts\logs\server.pid is only the npm wrapper. Killing it leaves an
# orphaned grandchild still listening on 8080 and still serving the OLD
# configuration, which silently invalidates any experiment that follows.
#
# So this targets the actual port owner, and - per the tester agent's diagnosis -
# re-reads the owner AFTER killing, because `tsx` can respawn a new child pid.
# The earlier version issued one kill, waited 2 s, and reported success even when
# the socket survived, which cost the tester more than one cycle.

param(
    [int]$Port = 8080,
    [int]$Attempts = 6,
    [int]$WaitSeconds = 2,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Continue'

function Get-PortOwner {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $conn) { return $null }
    return $conn.OwningProcess
}

for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
    $owner = Get-PortOwner
    if (-not $owner) {
        Write-Output "port $Port is free (attempt $attempt)"
        exit 0
    }

    Write-Output "attempt ${attempt}: checking pid $owner on port $Port"
    # A separate project can bind a more-specific loopback address while the
    # replica still owns 0.0.0.0. Never kill Docker or an unrelated port owner.
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$owner"
    $replicaRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) 'server-ts').Replace('\', '/').ToLowerInvariant()
    $command = ([string]$processInfo.CommandLine).Replace('\', '/').ToLowerInvariant()
    if ($processInfo.Name -ne 'node.exe' -or -not $command.Contains($replicaRoot + '/') -or
        $command -notmatch '(?:src/server\.(?:ts|js))') {
        Write-Output "REFUSED: pid $owner is not an identified replica process ($($processInfo.Name)); inspect the port conflict without stopping it."
        exit 1
    }
    if ($CheckOnly) {
        Write-Output "verified replica owner pid $owner; CheckOnly leaves it running"
        exit 0
    }
    Write-Output "stopping verified replica pid $owner"
    try {
        # -ErrorAction Stop so a failed kill is visible instead of silent.
        Stop-Process -Id $owner -Force -ErrorAction Stop
    } catch {
        Write-Output "  kill failed: $($_.Exception.Message)"
    }

    Start-Sleep -Seconds $WaitSeconds

    # Re-read rather than trusting the pid we just killed: tsx may have
    # respawned the listener under a new pid.
    $after = Get-PortOwner
    if ($after -eq $owner) {
        Write-Output "  pid $owner still holding the port"
    } elseif ($after) {
        Write-Output "  listener respawned as pid $after; will retry"
    }
}

$owner = Get-PortOwner
if ($owner) {
    Write-Output "FAILED: port $Port is still held by pid $owner after $Attempts attempts"
    exit 1
}
Write-Output "port $Port released"
exit 0
