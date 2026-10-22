$ErrorActionPreference = 'Stop'
foreach ($name in @('py', 'java', 'adb', 'docker', 'git', 'node')) {
    $found = Get-Command $name -ErrorAction SilentlyContinue
    [pscustomobject]@{ Tool = $name; Available = [bool]$found; Path = $found.Source }
}
if (Test-Path (Join-Path $PSScriptRoot '../.venv/Scripts/python.exe')) {
    & (Join-Path $PSScriptRoot '../.venv/Scripts/python.exe') --version
}

