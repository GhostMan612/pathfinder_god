# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
<#
.SYNOPSIS
    Run the Spoke instrumented suite on a physical device, deterministically.

.DESCRIPTION
    `:app:connectedDebugAndroidTest` does not wake the handset. On a long run the
    screen times out, Android drops the launched Activity out of the foreground, and
    every Compose test fails with "No compose hierarchies found in the app" -- a
    device-state failure that looks exactly like 29 broken tests. A full-suite pass
    was green twice and then failed 29/53 this way, purely because the phone slept.

    This script asserts the preconditions the suite actually needs (awake, unlocked,
    stay-on), runs the lane, then restores the device's stay-on setting. It never
    modifies the app, never touches release tasks, and always uses --no-daemon.

.PARAMETER Serial
    adb serial to target. Defaults to the single attached device.

.PARAMETER Filter
    Optional instrumentation class filter, e.g. ...LanHubSmokeTest.

.PARAMETER Jdk
    JAVA_HOME to launch Gradle with. Defaults to the Studio-provisioned Temurin 17.

.EXAMPLE
    .\scripts\device-test.ps1
    .\scripts\device-test.ps1 -Serial 7040016025040287
#>
[CmdletBinding()]
param(
    [string]$Serial,
    [string]$Filter,
    [string]$Jdk = 'C:\android\Android Studio\jbr\jdks\eclipse_adoptium-17-amd64-windows.2'
)

$ErrorActionPreference = 'Stop'
$spoke = Split-Path -Parent $PSScriptRoot
Set-Location $spoke

function Resolve-Adb {
    # Join-Path throws on a null base, and ANDROID_HOME/ANDROID_SDK_ROOT are often
    # unset on a machine where adb is already on PATH. Build the list defensively.
    $candidates = @()
    foreach ($root in @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, 'C:\android\sdk')) {
        if ([string]::IsNullOrWhiteSpace($root)) { continue }
        $candidates += (Join-Path $root 'platform-tools\adb.exe')
    }
    $candidates = @($candidates | Where-Object { Test-Path $_ })
    if ($candidates.Count -gt 0) { return $candidates[0] }
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw 'adb not found. Set ANDROID_HOME or put platform-tools on PATH.'
}

$adb = Resolve-Adb

if (-not $Serial) {
    # @() is load-bearing: with a single attached device, Select-String output is one
    # string, and $string[0] is its FIRST CHARACTER. That turned the only serial
    # "7040016025040287" into "7" and every adb call targeted a device that cannot exist.
    $attached = @(& $adb devices | Select-String -Pattern '^\S+\s+device$' | ForEach-Object {
        ($_ -split '\s+')[0]
    })
    if ($attached.Count -eq 0) {
        throw 'No device attached (adb devices shows none in "device" state).'
    }
    if ($attached.Count -gt 1) {
        throw "Multiple devices attached ($($attached -join ', ')). Pass -Serial explicitly."
    }
    $Serial = $attached[0]
}

function Invoke-Adb {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $out = & $adb -s $Serial @Args 2>&1
    return ($out | Out-String).Trim()
}

if (-not (Test-Path (Join-Path $Jdk 'bin\java.exe'))) {
    throw "JAVA_HOME candidate has no bin\java.exe: $Jdk"
}

Write-Host "[device-test] serial  : $Serial"
Write-Host "[device-test] jdk     : $Jdk"

# --- Preconditions -----------------------------------------------------------
# stayon MUST come first. Without it the handset returns to doze within seconds,
# so a wake-then-verify sequence observes "Asleep" and gives up on a device that
# would have stayed awake had the setting been applied. `svc power stayon true`
# persists until unplugged/reboot, so it outlives this process and is restored below.
$previousStayOn = Invoke-Adb shell settings get global stay_on_while_plugged_in
Invoke-Adb shell svc power stayon true | Out-Null

Invoke-Adb shell input keyevent KEYCODE_WAKEUP | Out-Null
Start-Sleep -Milliseconds 800
# An expanded notification shade also holds focus as NotificationShade, which is
# indistinguishable from a keyguard at the window level. Collapse it explicitly.
Invoke-Adb shell cmd statusbar collapse | Out-Null
Invoke-Adb shell wm dismiss-keyguard | Out-Null
Start-Sleep -Milliseconds 800

$wakefulness = Invoke-Adb shell dumpsys power
if ($wakefulness -notmatch 'mWakefulness=Awake') {
    throw "Device did not wake (mWakefulness not Awake). Unlock it manually and retry."
}

# The suite launches Activities; if the keyguard is still up they never reach the
# foreground and Compose reports "No compose hierarchies found in the app".
$focus = Invoke-Adb shell dumpsys window
if ($focus -match 'mCurrentFocus=.*(NotificationShade|Keyguard)') {
    throw 'Keyguard is still showing (device is locked with a PIN/pattern). Unlock it and retry.'
}

$log = Join-Path $env:TEMP ("pfg-device-test-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$resultsDir = Join-Path $spoke 'app\build\outputs\androidTest-results\connected'
if (Test-Path $resultsDir) { Remove-Item -Recurse -Force $resultsDir -ErrorAction SilentlyContinue }

$gradleArgs = @(':app:connectedDebugAndroidTest', '--no-daemon', '--console=plain')
if ($Filter) {
    $gradleArgs += "-Pandroid.testInstrumentationRunnerArguments.class=$Filter"
}

$env:JAVA_HOME = $Jdk
# ANDROID_SERIAL is the supported selector for connectedAndroidTest. There is no
# `serial` instrumentation argument: passing one would leak into the test bundle
# as an inert extra and imply a mechanism that does not exist.
$env:ANDROID_SERIAL = $Serial

try {
    Write-Host "[device-test] running  : $($gradleArgs -join ' ')"
    # Start-Process with file redirection, not `*>`: under $ErrorActionPreference='Stop',
    # PowerShell 5.1 turns ANY stderr line from a native command (here: the harmless
    # "SDK XML version 4" warning) into a terminating NativeCommandError, so the suite
    # would abort before a single test ran.
    $stdoutFile = "$log.stdout"
    $stderrFile = "$log.stderr"
    $proc = Start-Process -FilePath (Join-Path $spoke 'gradlew.bat') `
        -ArgumentList $gradleArgs `
        -WorkingDirectory $spoke `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdoutFile `
        -RedirectStandardError $stderrFile
    $code = $proc.ExitCode
    Get-Content -LiteralPath $stdoutFile, $stderrFile -ErrorAction SilentlyContinue |
        Set-Content -LiteralPath $log -Encoding UTF8
    Remove-Item -LiteralPath $stdoutFile, $stderrFile -ErrorAction SilentlyContinue
}
finally {
    if ($previousStayOn -and $previousStayOn -ne 'null') {
        Invoke-Adb shell settings put global stay_on_while_plugged_in $previousStayOn | Out-Null
    }
    else {
        Invoke-Adb shell svc power stayon false | Out-Null
    }
}

$tests = 0; $failures = 0; $errors = 0; $skipped = 0
$xmls = Get-ChildItem -Recurse -Filter '*.xml' -Path $resultsDir -ErrorAction SilentlyContinue
foreach ($x in $xmls) {
    try {
        [xml]$doc = Get-Content -LiteralPath $x.FullName
        if ($doc.testsuite) {
            $tests += [int]$doc.testsuite.tests
            $failures += [int]$doc.testsuite.failures
            $errors += [int]$doc.testsuite.errors
            $skipped += [int]$doc.testsuite.skipped
        }
    }
    catch { }
}

Write-Host ''
Write-Host "[device-test] exit    : $code"
Write-Host "[device-test] tests   : $tests  failures=$failures errors=$errors skipped=$skipped"
Write-Host "[device-test] log     : $log"
if ($code -ne 0) {
    Select-String -Path $log -Pattern 'FAILED|Exception|BUILD FAILED' |
        ForEach-Object { $_.Line.Trim() } | Select-Object -First 25 | ForEach-Object { Write-Host "  $_" }
}
exit $code
