# Etapa 5: frontend + proxy + API con Docker Compose
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
docker compose up -d --build backend frontend proxy
Start-Sleep 5
docker compose ps
Write-Host "Aplicación: http://localhost:8080   API: http://localhost:8080/api/categorias" -ForegroundColor Green
