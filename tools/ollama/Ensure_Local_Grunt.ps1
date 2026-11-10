# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Make the local grunt usable without starting the whole Pathfinder God stack.
# Windows 11 is hostile to 11434 on this machine, so everything stays on 11450.

$ErrorActionPreference = 'Stop'
$port = 11450
$env:OLLAMA_HOST = "127.0.0.1:$port"

$ollama = Get-Command 'ollama.exe' -ErrorAction SilentlyContinue
if (-not $ollama) {
    throw 'ollama.exe is not on PATH.'
}

$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Write-Host "Starting Ollama on 127.0.0.1:$port ..."
    Start-Process -FilePath $ollama.Source -ArgumentList 'serve' -WindowStyle Hidden
}

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/tags" -TimeoutSec 2
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    throw "Ollama did not answer on 127.0.0.1:$port."
}

& (Join-Path $PSScriptRoot 'Create_Local_Grunt.ps1')

# Load the model once so the first local_grunt call is not a cold start.
Write-Host 'Warming pf-grunt:3b ...'
$warm = @{
    model      = 'pf-grunt:3b'
    stream     = $false
    keep_alive = '30m'
    options    = @{ num_predict = 1; temperature = 0 }
    messages   = @(@{ role = 'user'; content = 'ok' })
} | ConvertTo-Json -Depth 8
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/chat" -Method Post -Body $warm -ContentType 'application/json' -TimeoutSec 300
} catch {
    throw "pf-grunt:3b did not warm up on 127.0.0.1:${port}: $($_.Exception.Message)"
}

Write-Host 'Local grunt ready: local_grunt -> pf-grunt:3b on 127.0.0.1:11450'
exit 0
