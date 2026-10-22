$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
& (Join-Path $projectRoot '.venv/Scripts/python.exe') -m idea_echo_desktop.app --data-dir (Join-Path $projectRoot 'data/desktop')
exit $LASTEXITCODE
