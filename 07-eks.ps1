# Etapa 7: crea clúster EKS en FLOCI (k3s) y despliega la app con imágenes de ECR
$ErrorActionPreference = "Stop"; Set-Location $PSScriptRoot
$name = "lomax-eks"
.\aws.ps1 iam create-role --role-name eks-role --assume-role-policy-document '{\"Version\":\"2012-10-17\",\"Statement\":[]}' 2>$null | Out-Null
try { .\aws.ps1 eks create-cluster --name $name --role-arn arn:aws:iam::000000000000:role/eks-role --resources-vpc-config subnetIds=subnet-00000001 } catch { Write-Host "cluster ya existe o error: $_" }
for ($i = 0; $i -lt 90; $i++) {
    $st = (.\aws.ps1 eks describe-cluster --name $name --query cluster.status --output text).Trim()
    Write-Host "estado clúster: $st"; if ($st -eq "ACTIVE") { break }; Start-Sleep 5
}
.\aws.ps1 eks update-kubeconfig --name $name --kubeconfig "$PWD\k8s\kubeconfig"
Write-Host "kubeconfig en k8s\kubeconfig (si el servidor apunta a localhost, funciona desde este PC)"
$floci = (docker inspect floci --format "{{(index .NetworkSettings.Networks \"lomax-net\").IPAddress}}").Trim()
$img = @{}; Get-Content k8s\imagenes.env | ForEach-Object { $k, $v = $_ -split "=", 2; $img[$k] = $v }
Get-ChildItem k8s\*.yaml | ForEach-Object {
    (Get-Content $_.FullName -Raw).Replace("__ECR_BACKEND__", $img["lomax-backend"]).Replace("__ECR_FRONTEND__", $img["lomax-frontend"]).Replace("__ECR_PROXY__", $img["lomax-proxy"]).Replace("__FLOCI_IP__", $floci) |
        Set-Content -Encoding utf8 (Join-Path $env:TEMP $_.Name)
}
.\kubectl.ps1 apply -f "$env:TEMP\00-namespace.yaml"
.\kubectl.ps1 apply -f "$env:TEMP\10-backend.yaml" -f "$env:TEMP\20-frontend.yaml" -f "$env:TEMP\30-proxy.yaml"
.\kubectl.ps1 -n lomax get pods -o wide
Write-Host "Acceso: .\kubectl.ps1 -n lomax port-forward svc/proxy 8081:80   ->  http://localhost:8081" -ForegroundColor Green
