# EN LA UNIVERSIDAD (sin internet o con internet lento): carga las imágenes guardadas
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
docker load -i imagenes-offline\todas.tar
Write-Host "Imágenes cargadas. Continúe con .\iniciar-todo.ps1" -ForegroundColor Green
