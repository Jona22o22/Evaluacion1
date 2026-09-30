# EN CASA (con internet): guarda todas las imágenes base en imagenes-offline\*.tar para llevarlas en USB
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force imagenes-offline | Out-Null
$imgs = @("floci/floci:latest", "postgres:16-alpine", "public.ecr.aws/lambda/python:3.12", "registry:2", "rancher/k3s:latest",
          "python:3.12-slim", "nginx:1.27-alpine", "amazon/aws-cli:latest", "bitnami/kubectl:latest", "floci/floci-ui:latest")
foreach ($i in $imgs) { Write-Host "pull $i"; docker pull $i }
docker compose build backend frontend proxy
$imgs += @("lomax-backend:local", "lomax-frontend:local", "lomax-proxy:local")
docker save -o imagenes-offline\todas.tar @imgs
Write-Host "Listo: imagenes-offline\todas.tar (puede pesar varios GB)" -ForegroundColor Green
