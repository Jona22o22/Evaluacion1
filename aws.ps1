# Uso: .\aws.ps1 s3 ls      (usa AWS CLI local si existe; si no, un contenedor con AWS CLI)
$env:AWS_ACCESS_KEY_ID = "test"; $env:AWS_SECRET_ACCESS_KEY = "test"; $env:AWS_DEFAULT_REGION = "us-east-1"
if (Get-Command aws -ErrorAction SilentlyContinue) {
    aws --endpoint-url http://localhost:4566 @args
} else {
    docker run --rm --network lomax-net -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test -e AWS_DEFAULT_REGION=us-east-1 `
        -v "${PWD}:/work" -w /work amazon/aws-cli --endpoint-url http://floci:4566 @args
}
