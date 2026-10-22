param([switch]$Release,[switch]$Verify)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
if(-not $env:ANDROID_HOME){$env:ANDROID_HOME=Join-Path $projectRoot '.tooling/android-sdk'}
$gradleBinary=Join-Path $projectRoot '.tooling/gradle-8.13/bin/gradle.bat'
[string[]]$buildTasks=@(if($Release){'assembleRelease'}else{'assembleDebug'})
if($Verify){$buildTasks+=@('testDebugUnitTest','lintDebug','assembleDebugAndroidTest')}
# Java 17's worker argument-file encoding must match this Windows host's native charset.
$javaProbe=New-Object System.Diagnostics.Process
$javaProbe.StartInfo.FileName=(Get-Command java).Source
$javaProbe.StartInfo.Arguments='-XshowSettings:properties -version'
$javaProbe.StartInfo.UseShellExecute=$false
$javaProbe.StartInfo.CreateNoWindow=$true
$javaProbe.StartInfo.RedirectStandardError=$true
$javaProbe.StartInfo.RedirectStandardOutput=$true
$javaProbe.Start() | Out-Null
$javaProperties=$javaProbe.StandardError.ReadToEnd()
$javaProbe.WaitForExit()
$nativeEncoding=if($javaProperties -match 'native.encoding\s*=\s*([^\r\n]+)'){$Matches[1].Trim()}else{'UTF-8'}
$javaProbe.Dispose()
if(-not $nativeEncoding){$nativeEncoding='UTF-8'}
$jvmArgs='-Dorg.gradle.jvmargs=-Xmx1536m -Dfile.encoding='+$nativeEncoding
if(Test-Path -LiteralPath $gradleBinary){& $gradleBinary -p android -g (Join-Path $projectRoot '.tooling/gradle-home') --no-daemon $jvmArgs @buildTasks --console=plain}
else{& (Join-Path $projectRoot 'android/gradlew.bat') -p android -g (Join-Path $projectRoot '.tooling/gradle-home') --no-daemon $jvmArgs @buildTasks --console=plain}
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
$apkFolder=if($Release){'android/app/build/outputs/apk/release'}else{'android/app/build/outputs/apk/debug'}
Get-ChildItem -LiteralPath $apkFolder -Filter '*.apk' | ForEach-Object {Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName}
if($Release){Write-Output 'Release must be signed with your own persistent key before installation; never replace it with the debug key.'}
