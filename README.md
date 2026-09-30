# Lomax SA – Catálogo de productos en FLOCI

**Docker + Kubernetes + AWS (emulado localmente con FLOCI)**

Sistema de registro y consulta de productos compuesto por **Frontend + Proxy + API (Flask)**, con **RDS (PostgreSQL)**, **DynamoDB**, **S3** y **Lambda** (miniaturas). Las imágenes se publican en **ECR** y se despliegan en **EKS**.

---

## Tabla de contenido

1. [Requisitos](#1-requisitos)
2. [Arranque rápido](#2-arranque-rápido)
3. [Etapas, scripts y evidencias](#3-etapas--scripts--evidencias)
4. [Verificación E2 (RDS y DynamoDB)](#4-verificación-e2-rds-y-dynamodb)
5. [Verificación E3 (S3 y Lambda)](#5-verificación-e3-s3-y-lambda)
6. [EKS: escalamiento, autorrecuperación y persistencia (E7)](#6-eks-escalamiento-autorrecuperación-y-persistencia-e7)
7. [Solución de problemas](#7-solución-de-problemas)
8. [Estructura del proyecto](#8-estructura-del-proyecto)
9. [Validación en entorno real](#9-validación-en-entorno-real)

---

## 1. Requisitos

| Necesita | Detalle |
|---|---|
| **Docker Desktop** (Windows) | Con WSL2 / contenedores Linux y **≥ 6 GB de RAM** asignada. Es lo único obligatorio. |
| **PowerShell** | Ya viene con Windows. |
| **Internet** | Solo la primera vez, para descargar las imágenes. |
| Python / AWS CLI / kubectl | **No obligatorios**: los scripts usan contenedores (`aws.ps1`, `kubectl.ps1`). |

> [!NOTE]
> Si PowerShell bloquea los scripts, ejecute `Set-ExecutionPolicy -Scope Process Bypass` (solo dura esa ventana).

**Puertos usados:**

| Puerto | Uso |
|---|---|
| `4566` | FLOCI |
| `8080` | Aplicación |
| `7000-7099` | RDS de FLOCI |

## 2. Arranque rápido

```powershell
cd lomax
Set-ExecutionPolicy -Scope Process Bypass
.\iniciar-todo.ps1        # Floci + recursos + app + 20 productos
```

Abra <http://localhost:8080>. Repetir `iniciar-todo.ps1` es seguro (idempotente, no duplica registros).

## 3. Etapas → scripts → evidencias

| Etapa | Qué hacer | Comando | Guardar en |
|---|---|---|---|
| **E1** Diseño | Dibujar el diagrama con íconos AWS y explicarlo | – | `evidencias/E1` |
| **E2** RDS + DynamoDB | Crear y cargar; probar restricciones | `.\02-aprovisionar.ps1` + sección 4 | `evidencias/E2` |
| **E3** S3 + Lambda | Invocar Lambda, listar, get-object, dimensiones | Sección 5 | `evidencias/E3` |
| **E4** API | Reporte de todos los endpoints | `.\05-pruebas-api.ps1` (genera `reporte.txt`) | `evidencias/E4` |
| **E5** Frontend | Registrar desde el formulario y capturas | <http://localhost:8080> | `evidencias/E5` |
| **E6** ECR | Construir imágenes, etiquetar y hacer push | `.\06-ecr.ps1` | `evidencias/E6` |
| **E7** EKS | Pods, escalar 1→3, borrar pod, persistencia | `.\kubectl.ps1 apply -f k8s/...` + sección 6 | `evidencias/E7` |

## 4. Verificación E2 (RDS y DynamoDB)

**Localizar el contenedor de Postgres y consultar:**

```powershell
docker ps --filter "ancestor=postgres:16-alpine" --format "{{.Names}}"
$db = "<nombre-del-contenedor-postgres>"

docker exec $db psql -U lomax -d lomax -c "SELECT producto_id,codigo,nombre,precio,estado FROM productos ORDER BY 1 LIMIT 5;"
```

**Restricciones (las tres deben dar error):**

```powershell
# precio negativo
docker exec $db psql -U lomax -d lomax -c "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id) VALUES('X1','a','b',-1,1);"
# código duplicado
docker exec $db psql -U lomax -d lomax -c "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id) VALUES('LMX-TEC-001','a','b',1,1);"
# categoría inexistente
docker exec $db psql -U lomax -d lomax -c "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id) VALUES('X2','a','b',1,99);"
```

**DynamoDB** (un teclado y una pantalla, con atributos distintos):

```powershell
'{"producto_id":{"S":"1"}}' | Set-Content -Encoding ascii evidencias\E2\key1.json
'{"producto_id":{"S":"9"}}' | Set-Content -Encoding ascii evidencias\E2\key9.json
.\aws.ps1 dynamodb get-item --table-name producto_atributos --key file://evidencias/E2/key1.json
.\aws.ps1 dynamodb get-item --table-name producto_atributos --key file://evidencias/E2/key9.json
```

**Persistencia:** reinicie RDS sin borrar volúmenes y repita las consultas.

```powershell
docker restart $db
```

## 5. Verificación E3 (S3 y Lambda)

```powershell
.\aws.ps1 s3 ls
.\aws.ps1 s3 ls s3://lomax-originales/originales/
.\aws.ps1 s3 ls s3://lomax-miniaturas/miniaturas/
```

**Invocar la Lambda manualmente:**

```powershell
'{"producto_id":"1","bucket":"lomax-originales","key":"originales/1.jpg","bucket_miniaturas":"lomax-miniaturas"}' | Set-Content -Encoding ascii evidencias\E3\evento.json
.\aws.ps1 lambda invoke --function-name lomax-miniatura --cli-binary-format raw-in-base64-out --payload file://evidencias/E3/evento.json evidencias/E3/salida.json
Get-Content evidencias\E3\salida.json
```

Resultado esperado: `"ok": true`, original `[1200, 800]`, miniatura `[300, 200]`.

**Descargar y comprobar dimensiones:**

```powershell
.\aws.ps1 s3api get-object --bucket lomax-miniaturas --key miniaturas/1.jpg evidencias/E3/mini1.jpg
.\aws.ps1 s3api get-object --bucket lomax-originales --key originales/1.jpg evidencias/E3/orig1.jpg
Add-Type -AssemblyName System.Drawing
foreach($f in "orig1","mini1"){ $i=[System.Drawing.Image]::FromFile("$PWD\evidencias\E3\$f.jpg"); "$f $($i.Width)x$($i.Height)"; $i.Dispose() }
```

## 6. EKS: escalamiento, autorrecuperación y persistencia (E7)

```powershell
.\kubectl.ps1 -n lomax get pods -o wide
.\kubectl.ps1 -n lomax get pod -l app=backend -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IMAGEN:.spec.containers[0].image
.\kubectl.ps1 -n lomax scale deployment backend --replicas=3
.\kubectl.ps1 -n lomax get pods -w
```

**Solicitudes atendidas por cada pod:**

```powershell
1..12 | % { (Invoke-WebRequest -UseBasicParsing http://localhost:8081/api/instancia).Content }
.\kubectl.ps1 -n lomax logs -l app=backend --prefix --tail=5
```

**Autorrecuperación:** borre un pod y compare el UID del reemplazo.

```powershell
.\kubectl.ps1 -n lomax delete pod <nombre-pod-backend>
.\kubectl.ps1 -n lomax rollout restart deployment backend
```

**Acceso a la app en Kubernetes** (deje la ventana abierta):

```powershell
.\kubectl.ps1 -n lomax port-forward svc/proxy 8081:80
```

Luego abra <http://localhost:8081>.

## 7. Solución de problemas

| Síntoma | Solución |
|---|---|
| `docker` no responde | Abrir Docker Desktop y esperar a que diga "Engine running". |
| `provision.py` se queda en "esperando conexión" | `docker compose logs floci` y `docker ps -a`; comprobar que existe el contenedor de Postgres. |
| 502 con `paso: lambda` | La red de Lambda debe ser `lomax-net` (ver `FLOCI_SERVICES_LAMBDA_DOCKER_NETWORK`). |
| Timeout al subir imágenes (ECR) | Forzar el registro a `127.0.0.1:4566` para evitar el DNS IPv6 de Windows. |
| Error de kubeconfig en `kubectl` | Generar el config localmente apuntando a `localhost:4566` y aplicar los `.yaml` directamente. |

## 8. Estructura del proyecto

```text
lomax/
├── backend/     API (Flask) + Dockerfile
├── frontend/    Vistas (HTML, JS, CSS)
├── proxy/       Configuración NGINX
├── lambda/      Función de recorte de imágenes + zip precompilado
├── db/          Modelo schema.sql
├── scripts/     Aprovisionamiento, carga de datos y pruebas
├── k8s/         Manifiestos de Kubernetes
└── evidencias/  Capturas, archivos JSON y logs de validación
```

## 9. Validación en entorno real

Probado en **FLOCI real**, Windows 11 con Docker Desktop. Validado el **30 de septiembre de 2026**.

| Etapa | Resultado |
|---|---|
| **E2** RDS + DynamoDB | Las transacciones inválidas se rechazaron; las restricciones SQL están activas y no quedan registros parciales. |
| **E3** S3 + Lambda | Invocación manual exitosa; imágenes redimensionadas a 300×200 px. |
| **E4 / E5** API y Frontend | Todos los endpoints pasaron las pruebas y la app permitió registrar productos por la interfaz. |
| **E6** ECR | Problema de timeout DNS resuelto usando `127.0.0.1:4566`. Imágenes con etiqueta `991f1a0` subidas al registro emulado. |
| **E7** EKS | Tras configurar el clúster localmente, los manifiestos se aplicaron y los pods respondieron al balanceo de carga en el puerto 8081. |
