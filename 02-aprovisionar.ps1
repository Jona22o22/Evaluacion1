# Etapas 2 y 3: crea S3, DynamoDB, RDS (+esquema) y Lambda. Repetible sin duplicar.
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
docker compose --profile tools build tools
docker compose --profile tools run --rm tools /work/scripts/provision.py
