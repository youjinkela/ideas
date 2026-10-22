param([string]$OutputFile)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
if(-not $OutputFile){$OutputFile=Join-Path $projectRoot ('artifacts/idea-echo-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.zip')}
& (Join-Path $projectRoot '.venv/Scripts/python.exe') -m idea_echo.backup create --data-dir (Join-Path $projectRoot 'data/server') --file $OutputFile
exit $LASTEXITCODE
