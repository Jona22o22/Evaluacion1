# Comprueba que el PC (casa o universidad) puede correr el proyecto
Write-Host "== Requisitos ==" -ForegroundColor Cyan
docker version --format "Docker cliente {{.Client.Version}} / servidor {{.Server.Version}}" 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "Docker no está corriendo. Abra Docker Desktop y espere a que diga 'Engine running'." -ForegroundColor Red; exit 1 }
docker compose version
Write-Host "Memoria asignada a Docker (GB):" ([math]::Round((docker info --format "{{.MemTotal}}") / 1GB, 1)) "(recomendado >= 6)"
$aws = Get-Command aws -ErrorAction SilentlyContinue
if ($aws) { Write-Host "AWS CLI local: OK" } else { Write-Host "AWS CLI no instalado: use .\aws.ps1 (funciona con Docker)" -ForegroundColor Yellow }
$kc = Get-Command kubectl -ErrorAction SilentlyContinue
if ($kc) { Write-Host "kubectl local: OK" } else { Write-Host "kubectl no instalado: use .\kubectl.ps1 (funciona con Docker)" -ForegroundColor Yellow }
Write-Host "Puertos en uso (deben estar libres): 4566, 8080"
Get-NetTCPConnection -LocalPort 4566,8080 -State Listen -ErrorAction SilentlyContinue | Format-Table LocalPort,OwningProcess
