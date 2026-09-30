# Etapa 7: crea cluster EKS en FLOCI (k3s) y despliega la app con imagenes de ECR
$ErrorActionPreference = "Continue"; Set-Location $PSScriptRoot
$name = "lomax-eks"
$subs = ((.\aws.ps1 ec2 describe-subnets --query "Subnets[0:2].SubnetId" --output text) -split "\s+" | Where-Object { $_ }) -join ","
if (-not $subs) { throw "No hay subredes en FLOCI (ec2 describe-subnets vacio)" }
Write-Host "Subredes: $subs"
.\aws.ps1 iam create-role --role-name eks-role --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[]}' 2>$null | Out-Null
.\aws.ps1 eks create-cluster --name $name --role-arn arn:aws:iam::000000000000:role/eks-role --resources-vpc-config subnetIds=$subs
if ($LASTEXITCODE -ne 0) { Write-Host "cluster ya existe o error (revisar arriba)" }
$st = ""
for ($i = 0; $i -lt 90; $i++) {
    $st = "$(.\aws.ps1 eks describe-cluster --name $name --query cluster.status --output text)".Trim()
    Write-Host "estado cluster: $st"
    if ($st -eq "ACTIVE") { break }
    if ($i -ge 2 -and -not $st) { throw "El cluster no existe: revisar el error de create-cluster" }
    Start-Sleep 5
}
if ($st -ne "ACTIVE") { throw "El cluster no llego a ACTIVE" }

.\aws.ps1 eks update-kubeconfig --name $name --kubeconfig k8s/kubeconfig
if (-not (Test-Path k8s\kubeconfig)) { throw "No se creo k8s\kubeconfig" }
Write-Host "kubeconfig en k8s\kubeconfig (si el servidor apunta a localhost, funciona desde este PC)"
docker cp floci-eks-lomax-eks:/etc/rancher/k3s/k3s.yaml k8s/kubeconfig-admin
(Get-Content k8s\kubeconfig-admin) -replace 'https://127.0.0.1:6443','https://localhost:6500' | Set-Content -Encoding ascii k8s\kubeconfig

$redes = (docker inspect floci --format "{{json .NetworkSettings.Networks}}") | ConvertFrom-Json
$floci = $redes.'lomax-net'.IPAddress
if (-not $floci) { throw "No se obtuvo la IP de floci en lomax-net" }
Write-Host "IP de floci: $floci"

$img = @{}; Get-Content k8s\imagenes.env | ForEach-Object { $k, $v = $_ -split "=", 2; $img[$k] = $v }
Get-ChildItem k8s\*.yaml | ForEach-Object {
    (Get-Content $_.FullName -Raw).Replace("__ECR_BACKEND__", $img["lomax-backend"]).Replace("__ECR_FRONTEND__", $img["lomax-frontend"]).Replace("__ECR_PROXY__", $img["lomax-proxy"]).Replace("__FLOCI_IP__", $floci) |
        Set-Content -Encoding utf8 (Join-Path $env:TEMP $_.Name)
}
.\kubectl.ps1 apply -f "$env:TEMP\00-namespace.yaml"
if ($LASTEXITCODE -ne 0) { throw "Fallo apply del namespace" }
.\kubectl.ps1 apply -f "$env:TEMP\10-backend.yaml" -f "$env:TEMP\20-frontend.yaml" -f "$env:TEMP\30-proxy.yaml"
if ($LASTEXITCODE -ne 0) { throw "Fallo apply de los manifiestos" }
.\kubectl.ps1 -n lomax get pods -o wide
Write-Host "Acceso: .\kubectl.ps1 -n lomax port-forward svc/proxy 8081:80   ->  http://localhost:8081" -ForegroundColor Green
