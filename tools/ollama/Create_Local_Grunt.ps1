# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
# Build the local grunt model on the port Windows 11 leaves alone.
# Run after starting Ollama on 127.0.0.1:11450 (Ensure_Local_Grunt.ps1).

$ErrorActionPreference = 'Stop'
$env:OLLAMA_HOST = '127.0.0.1:11450'

$modelfile = Join-Path $PSScriptRoot 'Modelfile.local-grunt'
if (-not (Test-Path $modelfile)) {
    throw "Missing $modelfile"
}

ollama create pf-grunt:3b -f $modelfile
if ($LASTEXITCODE -ne 0) {
    throw "ollama create failed with exit code $LASTEXITCODE"
}

Write-Host 'Local grunt ready: pf-grunt:3b on 127.0.0.1:11450'
