# Lomax SA – Catálogo de productos en FLOCI (Docker + Kubernetes + AWS)

Sistema de registro y consulta de productos: Frontend + Proxy + API (Flask) con RDS (PostgreSQL), DynamoDB, S3 y Lambda (miniaturas), imágenes en ECR y despliegue en EKS, todo emulado localmente con FLOCI.

## 1. Requisitos

| Necesita | Detalle |
|---|---|
| **Docker Desktop (Windows)** | Con WSL2/Linux containers y >= 6 GB de RAM asignada. Es lo único obligatorio. |
| **PowerShell** | Ya viene con Windows. |
| **Internet** | Solo la 1.ª vez para descargar las imágenes. |
| **Python / AWS CLI / kubectl** | No obligatorios: los scripts usan contenedores (`aws.ps1`, `kubectl.ps1`). |

*Nota:* Si PowerShell bloquea scripts: `Set-ExecutionPolicy -Scope Process Bypass` (solo dura esa ventana). Puertos usados: `4566` (FLOCI), `8080` (aplicación), `7000-7099` (RDS de FLOCI).

## 2. Arranque rápido

```powershell
cd lomax
Set-ExecutionPolicy -Scope Process Bypass
.\iniciar-todo.ps1        # Floci + recursos + app + 20 productos
Abra http://localhost:8080. Repetir iniciar-todo.ps1 es seguro (idempotente, no duplica registros).3. Etapas → scripts → evidenciasEtapaQué hacerComandoGuardar enE1 DiseñoDibujar diagrama con íconos AWS y explicarlo–evidencias/E1E2 RDS+DynamoDBCrear y cargar; probar restricciones..\02-aprovisionar.ps1 + comandos sección 4evidencias/E2E3 S3+LambdaInvocar Lambda, listar, get-object, dimensionesComandos de la sección 5evidencias/E3E4 APIReporte de todos los endpoints..\05-pruebas-api.ps1 (genera reporte.txt)evidencias/E4E5 FrontendRegistrar desde el formulario y capturashttp://localhost:8080evidencias/E5E6 ECRConstruir imágenes, etiquetar y hacer push.\06-ecr.ps1evidencias/E6E7 EKSpods, escalar 1→3, borrar pod, persistencia..\kubectl.ps1 apply -f k8s/... + sección 6evidencias/E74. Comandos de verificación E2 (RDS y DynamoDB)PowerShell# Filas por estado y restricciones (SQL directo al contenedor RDS de FLOCI)
docker ps --filter "ancestor=postgres:16-alpine" --format "{{.Names}}"
$db = "<nombre-del-contenedor-postgres>"

docker exec $db psql -U lomax -d lomax -c "SELECT producto_id,codigo,nombre,precio,estado FROM productos ORDER BY 1 LIMIT 5;"
docker exec $db psql -U lomax -d lomax -c "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id) VALUES('X1','a','b',-1,1);"   # precio negativo -> error
docker exec $db psql -U lomax -d lomax -c "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id) VALUES('LMX-TEC-001','a','b',1,1);" # duplicado -> error
docker exec $db psql -U lomax -d lomax -c "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id) VALUES('X2','a','b',1,99);"        # categoría inexistente -> error

# DynamoDB
.\aws.ps1 dynamodb get-item --table-name producto_atributos --key '{\"producto_id\":{\"S\":\"1\"}}'
.\aws.ps1 dynamodb get-item --table-name producto_atributos --key '{\"producto_id\":{\"S\":\"9\"}}'

# Persistencia: reiniciar RDS SIN borrar volúmenes y repetir las consultas
docker restart $db
5. Comandos de verificación E3 (S3 + Lambda)PowerShell.\aws.ps1 s3 ls
.\aws.ps1 s3 ls s3://lomax-originales/originales/
.\aws.ps1 s3 ls s3://lomax-miniaturas/miniaturas/

# Invocar Lambda manualmente
'{"producto_id":"1","bucket":"lomax-originales","key":"originales/1.jpg","bucket_miniaturas":"lomax-miniaturas"}' | Set-Content -Encoding ascii evidencias\E3\evento.json
.\aws.ps1 lambda invoke --function-name lomax-miniatura --cli-binary-format raw-in-base64-out --payload file://evidencias/E3/evento.json evidencias/E3/salida.json
Get-Content evidencias\E3\salida.json          # debe mostrar "ok": true, original [1200,800], miniatura [300,200]

# Descargar y comprobar dimensiones
.\aws.ps1 s3api get-object --bucket lomax-miniaturas --key miniaturas/1.jpg evidencias/E3/mini1.jpg
.\aws.ps1 s3api get-object --bucket lomax-originales --key originales/1.jpg evidencias/E3/orig1.jpg
Add-Type -AssemblyName System.Drawing
foreach($f in "orig1","mini1"){ $i=[System.Drawing.Image]::FromFile("$PWD\evidencias\E3\$f.jpg"); "$f $($i.Width)x$($i.Height)"; $i.Dispose() }
6. Escalamiento, autorrecuperación y persistencia (EKS / E7)PowerShell.\kubectl.ps1 -n lomax get pods -o wide
.\kubectl.ps1 -n lomax get pod -l app=backend -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IMAGEN:.spec.containers[0].image
.\kubectl.ps1 -n lomax scale deployment backend --replicas=3
.\kubectl.ps1 -n lomax get pods -w

# Solicitudes por pod y logs
1..12 | % { (Invoke-WebRequest -UseBasicParsing http://localhost:8081/api/instancia).Content }
.\kubectl.ps1 -n lomax logs -l app=backend --prefix --tail=5

# Autorrecuperación: borre un pod, compare UID del reemplazo
.\kubectl.ps1 -n lomax delete pod <nombre-pod-backend>
.\kubectl.ps1 -n lomax rollout restart deployment backend
El acceso a la app orquestada en Kubernetes es .\kubectl.ps1 -n lomax port-forward svc/proxy 8081:80 (dejar ventana abierta) → http://localhost:8081.7. Solución de problemasSíntomaSolucióndocker no respondeAbrir Docker Desktop, esperar "Engine running".provision.py se queda en "esperando conexión"docker compose logs floci y docker ps -a; comprobar que existe postgres.502 con paso: lambdaLa red de Lambda debe ser lomax-net (ver FLOCI_SERVICES_LAMBDA_DOCKER_NETWORK).Timeout al subir imágenes (ECR)Forzar la IP en el script apuntando el registro a 127.0.0.1:4566 para evadir el DNS IPv6 de Windows.kubectl error de kubeconfigGenerar el config localmente apuntando a localhost:4566 y aplicar los archivos .yaml directamente.8. Estructura del Proyectobackend/: API (Flask) + Dockerfilefrontend/: Vistas (HTML, JS, CSS)proxy/: Configuración NGINXlambda/: Función de recorte de imágenes + zip precompiladodb/: Modelo schema.sqlscripts/: Herramientas de aprovisionamiento, carga y pruebask8s/: Manifiestos de Kubernetesevidencias/: Capturas de pantalla, archivos JSON y logs de validación.9. Validación en Entorno RealProbado íntegramente en FLOCI real, Windows 11 con Docker Desktop, validado exitosamente el 30 de septiembre de 2026. Se lograron las siguientes metas:E2 (RDS+DynamoDB): Se rechazaron correctamente transacciones inválidas probando que las restricciones SQL están activas sin registros parciales.E3 (S3+Lambda): Invocación manual exitosa logrando el redimensionamiento de las imágenes a 300x200px.E4 / E5 (API y Frontend): Todos los endpoints pasaron las pruebas y la app permitió nuevos registros por UI.E6 (ECR): Solucionado problema de timeout DNS usando 127.0.0.1:4566. Las imágenes (etiqueta 991f1a0) se subieron al registro emulado.E7 (EKS): Tras configuración local manual del clúster, los manifiestos se aplicaron exitosamente y los pods respondieron al balanceo de carga local en el puerto 8081.
