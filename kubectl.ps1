# Uso: .\kubectl.ps1 get pods   (kubectl local, o contenedor con el kubeconfig del proyecto)
$kc = Join-Path $PSScriptRoot "k8s\kubeconfig"
$oldPath = $env:Path
$env:Path = "$PSScriptRoot\shim;$env:Path"
try {
    if (Get-Command kubectl -ErrorAction SilentlyContinue) { kubectl --kubeconfig $kc @args }
    else { docker run --rm --network lomax-net -v "${kc}:/kube/config:ro" -v "${PWD}:/work" -w /work -e KUBECONFIG=/kube/config bitnami/kubectl @args }
} finally { $env:Path = $oldPath }