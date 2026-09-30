# E4: prueba todos los endpoints y guarda evidencias\E4\reporte.txt
Set-Location $PSScriptRoot
docker compose --profile tools run --rm tools /work/scripts/test_endpoints.py
