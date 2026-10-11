# Resource selection is owned by the sibling Server checkout. Prepare its inactive
# E7 JSON profile; never mutate Instrumented environment, device or native files.
param([switch]$InspectOnly)
$ErrorActionPreference='Stop'
$episode07InstrumentedRoot=Split-Path $PSScriptRoot -Parent
$episode07ServerTool=Join-Path (Split-Path $episode07InstrumentedRoot -Parent) 'Blustone-Server/tools/episode07-resource-profile.ps1'
if(-not(Test-Path -LiteralPath $episode07ServerTool -PathType Leaf)){throw 'Sibling Blustone-Server profile preparation tool is missing'}
& $episode07ServerTool -InspectOnly:$InspectOnly
