param([switch]$Lan,[int]$Port=8000)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$env:IDEA_ECHO_DATA=Join-Path $projectRoot 'data/server'
$listenAddress=if($Lan){'0.0.0.0'}else{'127.0.0.1'}
& (Join-Path $projectRoot '.venv/Scripts/python.exe') -m uvicorn idea_echo.app:create_app --factory --host $listenAddress --port $Port --no-access-log
exit $LASTEXITCODE
