# Atajo: deja TODO funcionando (Floci + recursos + app + 20 productos). Tarda varios minutos la primera vez.
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
.\00-verificar-requisitos.ps1
.\01-levantar-floci.ps1
.\02-aprovisionar.ps1
.\03-levantar-app.ps1
.\04-cargar-datos.ps1
Write-Host "`nLISTO -> http://localhost:8080" -ForegroundColor Green
