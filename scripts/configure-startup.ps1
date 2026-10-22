param([switch]$Disable)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$runKey='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if($Disable){Remove-ItemProperty -LiteralPath $runKey -Name 'IdeaEcho' -ErrorAction SilentlyContinue;Write-Output '已关闭当前用户的点子回声自启动';exit}
$pythonWindowless=Join-Path $projectRoot '.venv/Scripts/pythonw.exe'
if(-not(Test-Path -LiteralPath $pythonWindowless)){throw '请先准备项目虚拟环境'}
$desktopData=Join-Path $projectRoot 'data/desktop'
$launchCommand='"'+$pythonWindowless+'" -m idea_echo_desktop.app --data-dir "'+$desktopData+'" --no-browser'
New-ItemProperty -LiteralPath $runKey -Name 'IdeaEcho' -Value $launchCommand -PropertyType String -Force | Out-Null
Write-Output '已启用当前用户登录时启动；程序保持后台运行，19:00提醒。可用 -Disable 撤销。'
