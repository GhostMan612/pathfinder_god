# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# One-click boot for the whole Pathfinder God stack:
#   1. Ollama brain (ollama serve) on 127.0.0.1:11450
#   2. Hub on :8000 serving the god
#   3. Command Center exe
# Safe to run more than once: it skips what is already listening.

$ErrorActionPreference = 'SilentlyContinue'
Set-Location 'C:\pathfinder_god'

# Snapshot campaign memory before the hub starts writing to it. The whole GM
# continuity - chronicle, combat scene, sessions, entity ledger - lives in this
# one file, and BP-07 Stage 4 made the hub write to it automatically.
$py = 'C:\venv-hub\venv\Scripts\python.exe'
if (Test-Path $py) {
    & $py 'C:\pathfinder_god\hub\scripts\backup_campaign.py' --keep 20
}

# The hub's .env expects Ollama at 127.0.0.1:11450 (not the default 11434), so pin it.
$env:OLLAMA_HOST = '127.0.0.1:11450'

# 1. Ollama
if (-not (Get-NetTCPConnection -LocalPort 11450 -State Listen)) {
    Start-Process -FilePath 'ollama.exe' -ArgumentList 'serve' `
        -WorkingDirectory 'C:\pathfinder_god' -WindowStyle Minimized
}

# 2. Hub
if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen)) {
    Start-Process -FilePath 'C:\venv-hub\venv\Scripts\python.exe' `
        -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' `
        -WorkingDirectory 'C:\pathfinder_god\hub' -WindowStyle Minimized
}

# Wait for the hub to answer
$ok = $false
1..60 | ForEach-Object {
    if (-not $ok) {
        try {
            $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2 -UseBasicParsing
            $ok = $true
        } catch { Start-Sleep -Seconds 1 }
    }
}
if ($ok) { Write-Host 'Hub is up.' } else { Write-Host 'Hub did NOT come up - see the minimized Hub window for the error.' }

# 3. Command Center
$cc = 'C:\pathfinder_god\tools\command_center\dist\PathfinderGodCommandCenter.exe'
if (Test-Path $cc) { Start-Process -FilePath $cc }
