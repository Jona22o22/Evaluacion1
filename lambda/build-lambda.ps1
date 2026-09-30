# Reconstruye lambda_thumbnail.zip con Docker (solo si modifica handler.py). Requiere internet (pip).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
docker run --rm -v "${PWD}:/w" -w /w --platform linux/amd64 python:3.12-slim sh -c "rm -rf pkg && pip install -q --target pkg Pillow==10.4.0 && cp handler.py pkg/ && cd pkg && python -c \"import zipfile,os;z=zipfile.ZipFile('../lambda_thumbnail.zip','w',zipfile.ZIP_DEFLATED);[z.write(os.path.join(r,f),os.path.relpath(os.path.join(r,f),'.')) for r,_,fs in os.walk('.') for f in fs if not f.endswith('.pyc')]\" && cd .. && rm -rf pkg"
Write-Host "lambda_thumbnail.zip generado"
