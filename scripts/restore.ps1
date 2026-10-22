param([Parameter(Mandatory=$true)][string]$BackupFile,[Parameter(Mandatory=$true)][string]$EmptyDestination)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
& (Join-Path $projectRoot '.venv/Scripts/python.exe') -m idea_echo.backup restore --file $BackupFile --destination $EmptyDestination
exit $LASTEXITCODE
