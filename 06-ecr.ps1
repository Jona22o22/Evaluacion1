# Etapa 6: crea repos ECR en FLOCI, construye, etiqueta (commit) y publica frontend, backend y proxy
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
$ver = "0.0.0"
if (Get-Command git -ErrorAction SilentlyContinue) { $h = git rev-parse --short HEAD 2>$null; if ($h) { $ver = $h } }
if ($ver -eq "0.0.0") { $ver = Get-Date -Format "yyyyMMdd-HHmm" }
Write-Host "Versión de imágenes: $ver"
docker compose build backend frontend proxy
$repos = @("lomax-backend", "lomax-frontend", "lomax-proxy")
$uris = @{}
foreach ($r in $repos) {
    .\aws.ps1 ecr create-repository --repository-name $r 2>$null | Out-Null
    $uri = (.\aws.ps1 ecr describe-repositories --repository-names $r --query "repositories[0].repositoryUri" --output text).Trim()
    $uris[$r] = $uri
    Write-Host "$r -> $uri"
}
$registry = ($uris["lomax-backend"] -split "/")[0]
Write-Host "Registro: $registry"
try { (.\aws.ps1 ecr get-login-password) | docker login --username AWS --password-stdin $registry } catch { Write-Host "login omitido (registro local sin autenticación)" }
foreach ($r in $repos) {
    $local = $r -replace "^lomax-", "lomax-"; $img = "$($r):local"
    docker tag $img "$($uris[$r]):$ver"
    docker push "$($uris[$r]):$ver"
}
$uris.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value):$ver" } | Set-Content -Encoding ascii k8s\imagenes.env
Write-Host "`nImágenes publicadas. Referencias guardadas en k8s\imagenes.env" -ForegroundColor Green
.\aws.ps1 ecr list-images --repository-name lomax-backend
.\aws.ps1 ecr describe-images --repository-name lomax-backend
