# chain-watcher.ps1 — laptop-side watcher for the Sovereign Council chain pilot
#
# WHAT IT DOES
#   Watches artifact-chain/review/findings/ in this repo. When Phoenix
#   (Muse) writes a new findings file there, this script prints a notice
#   and the exact `opencode` command to hand those findings to OpenCode.
#   It does NOT start OpenCode by itself, edit anything, or push — Glenn
#   runs the printed command when ready.
#
# SETUP (run on Glenn's laptop, from the repo root, once per session)
#   powershell -ExecutionPolicy Bypass -File tools\chain-watcher.ps1
#
#   Leave that window open; stop it with Ctrl+C. To run it in the
#   background at login instead, register a Scheduled Task (run once as
#   Administrator):
#     $action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
#       -Argument '-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\pathfinder_god\tools\chain-watcher.ps1"'
#     $trigger = New-ScheduledTaskTrigger -AtLogOn
#     Register-ScheduledTask -TaskName 'PathfinderChainWatcher' `
#       -Action $action -Trigger $trigger -Description 'Watches artifact-chain/review/findings for new council findings.'
#   (Adjust C:\pathfinder_god to the real repo path.)
#
# REQUIRES: Windows PowerShell 5.1+ or PowerShell 7, OpenCode on PATH
#   (`opencode --version` should print a version). No admin rights
#   needed for the foreground run.

param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$FindingsDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'artifact-chain\review\findings'),
    [string]$LogFile = (Join-Path $env:TEMP 'pathfinder-chain-watcher.log')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $FindingsDir)) {
    Write-Host "Findings dir not found: $FindingsDir" -ForegroundColor Red
    Write-Host 'Run this from the pathfinder_god repo (or pass -RepoRoot).'
    exit 1
}

Write-Host 'Pathfinder God council chain watcher' -ForegroundColor Cyan
Write-Host "  Watching: $FindingsDir"
Write-Host "  Log:      $LogFile"
Write-Host '  Press Ctrl+C to stop.'
Write-Host ''

function Write-Notice {
    param([string]$Message)
    $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $line = "[$stamp] $Message"
    Write-Host $line -ForegroundColor Yellow
    Add-Content -Path $LogFile -Value $line
}

# Baseline: files already here are old news, not new findings.
$seen = @{}
Get-ChildItem -Path $FindingsDir -File -Filter '*.md' |
    Where-Object { $_.Name -ne 'README.md' } |
    ForEach-Object { $seen[$_.FullName] = $true }

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $FindingsDir
$watcher.Filter = '*.md'
$watcher.IncludeSubdirectories = $false
$watcher.NotifyFilter = [System.IO.NotifyFilters]::FileName
$watcher.EnableRaisingEvents = $true

# Synchronous wait loop (WaitForChanged) rather than Register-ObjectEvent:
# event actions run in a separate scope where script variables are not
# visible, which is a classic source of silent no-ops. WaitForChanged
# keeps everything on this thread and is easy to reason about.
try {
    while ($true) {
        $change = $watcher.WaitForChanged(
            [System.IO.WatcherChangeTypes]::Created, 1000)
        if ($change.TimedOut) { continue }
        $path = Join-Path $FindingsDir $change.Name
        if ($change.Name -eq 'README.md') { continue }
        if ($seen.ContainsKey($path)) { continue }
        $seen[$path] = $true
        # Give the writer a moment to finish the file.
        Start-Sleep -Milliseconds 500
        $name = $change.Name
        Write-Host ''
        Write-Notice "NEW COUNCIL FINDINGS: $name"
        Write-Host '  File: ' -NoNewline -ForegroundColor Green
        Write-Host $path
        Write-Host ''
        Write-Host '  Hand them to OpenCode with:' -ForegroundColor Cyan
        Write-Host ("  opencode run `"Read artifact-chain/review/findings/$name and fix each finding in the same PR branch. Run pytest hub/tests/ and ruff check; commit with explicit paths; push the branch; do not merge.`"") -ForegroundColor White
        Write-Host ''
        Write-Host '  Or paste this into an open OpenCode session:' -ForegroundColor Cyan
        Write-Host "  Read artifact-chain/review/findings/$name and fix each finding in the same PR branch." -ForegroundColor White
        Write-Host ''
    }
}
finally {
    $watcher.Dispose()
}
