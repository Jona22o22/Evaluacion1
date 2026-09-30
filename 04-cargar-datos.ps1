# Carga 20 productos publicados (idempotente)
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
docker compose --profile tools run --rm tools /work/scripts/seed_productos.py
