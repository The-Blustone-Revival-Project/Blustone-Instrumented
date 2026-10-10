# Dot-source this file from PowerShell to put the Blustone analysis tools on PATH:
#   . .\tools\env.ps1

$blustoneRepoRoot = Split-Path $PSScriptRoot -Parent
$blustoneToolRoot = Join-Path $blustoneRepoRoot 'local/toolchains'
$blustoneJdk = Get-ChildItem -LiteralPath (Join-Path $blustoneToolRoot 'jdk') -Directory |
    Where-Object Name -like 'jdk-*' |
    Select-Object -First 1

if (-not $blustoneJdk) {
    throw 'Blustone Temurin JDK was not found under tools\jdk.'
}

$env:JAVA_HOME = $blustoneJdk.FullName
$env:ANDROID_HOME = Join-Path $blustoneToolRoot 'android-sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:ANDROID_AVD_HOME = Join-Path $blustoneRepoRoot 'local/avd'
$env:VIRTUAL_ENV = Join-Path $blustoneToolRoot 'python-venv'

$blustonePaths = @(
    (Join-Path $env:JAVA_HOME 'bin')
    (Join-Path $blustoneToolRoot 'jadx\bin')
    (Join-Path $blustoneToolRoot 'android-sdk\platform-tools')
    (Join-Path $blustoneToolRoot 'android-sdk\cmdline-tools\latest\bin')
    (Join-Path $blustoneToolRoot 'android-sdk\emulator')
    (Join-Path $blustoneToolRoot 'python-venv\Scripts')
)
$env:Path = (($blustonePaths + $env:Path) -join ';')

Write-Output "JAVA_HOME=$env:JAVA_HOME"
Write-Output "ANDROID_HOME=$env:ANDROID_HOME"
Write-Output "ANDROID_AVD_HOME=$env:ANDROID_AVD_HOME"
Write-Output "VIRTUAL_ENV=$env:VIRTUAL_ENV"
