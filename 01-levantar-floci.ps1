$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
docker compose up -d floci
Write-Host "Esperando a FLOCI..."
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -UseBasicParsing http://localhost:4566/_floci/health -TimeoutSec 2 | Out-Null; break }
    catch { try { Invoke-WebRequest -UseBasicParsing http://localhost:4566 -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 2 } }
}
docker compose ps
Write-Host "FLOCI listo en http://localhost:4566 (consola: http://localhost:4566/_floci/ui)" -ForegroundColor Green
