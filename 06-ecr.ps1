# Etapa 6: crea repos ECR en FLOCI, construye, etiqueta y publica frontend, backend y proxy
$ErrorActionPreference = "Continue"; Set-Location $PSScriptRoot
$ver = "0.0.0"
if (Get-Command git -ErrorAction SilentlyContinue) { $h = git rev-parse --short HEAD 2>$null; if ($h) { $ver = $h } }
if ($ver -eq "0.0.0") { $ver = Get-Date -Format "yyyyMMdd-HHmm" }
Write-Host "Version de imagenes: $ver"

docker compose build backend frontend proxy
if ($LASTEXITCODE -ne 0) { throw "Fallo el build" }

$repos = @("lomax-backend", "lomax-frontend", "lomax-proxy")
$uris = @{}
foreach ($r in $repos) {
    .\aws.ps1 ecr create-repository --repository-name $r 2>$null | Out-Null
    $uri = (.\aws.ps1 ecr describe-repositories --repository-names $r --query "repositories[0].repositoryUri" --output text).Trim()
    if (-not $uri) { throw "No se obtuvo la URI de $r" }
    $uris[$r] = $uri
    Write-Host "$r -> $uri"
}
$registry = ($uris["lomax-backend"] -split "/")[0]
Write-Host "Registro: $registry"

(.\aws.ps1 ecr get-login-password) | docker login --username AWS --password-stdin $registry
if ($LASTEXITCODE -ne 0) { Write-Host "login omitido (registro local sin autenticacion)" }

foreach ($r in $repos) {
    docker tag "$($r):local" "$($uris[$r]):$ver"
    if ($LASTEXITCODE -ne 0) { throw "Fallo el tag de $r" }
    docker push "$($uris[$r]):$ver"
    if ($LASTEXITCODE -ne 0) { throw "Fallo el push de $($uris[$r])" }
}

$uris.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value):$ver" } | Set-Content -Encoding ascii k8s\imagenes.env
Write-Host "`nImagenes publicadas. Referencias guardadas en k8s\imagenes.env" -ForegroundColor Green
.\aws.ps1 ecr list-images --repository-name lomax-backend
.\aws.ps1 ecr describe-images --repository-name lomax-backend