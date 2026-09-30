# Lomax SA – Catálogo de productos en FLOCI (Docker + Kubernetes + AWS)

Sistema de registro y consulta de productos: **Frontend + Proxy + API (Flask)** con **RDS (PostgreSQL)**, **DynamoDB**, **S3** y **Lambda** (miniaturas), imágenes en **ECR** y despliegue en **EKS**, todo emulado localmente con **FLOCI**.

## 1. Requisitos (casa y universidad)
| Necesita | Detalle |
|---|---|
| Docker Desktop (Windows) | Con **WSL2**/Linux containers y **>= 6 GB de RAM** asignada. Es lo único obligatorio. |
| PowerShell | Ya viene con Windows. |
| Internet | Solo la 1.ª vez (baja imágenes). **Para la universidad use el modo offline (sección 6).** |
| Python / AWS CLI / kubectl | **No obligatorios**: los scripts usan contenedores (`aws.ps1`, `kubectl.ps1`). |

Si PowerShell bloquea scripts: `Set-ExecutionPolicy -Scope Process Bypass` (solo dura esa ventana).
Puertos usados: **4566** (FLOCI), **8080** (aplicación), 7000-7099 (RDS de FLOCI).

## 2. Arranque rápido
```powershell
cd lomax
Set-ExecutionPolicy -Scope Process Bypass
.\iniciar-todo.ps1        # Floci + recursos + app + 20 productos
```
Abra **http://localhost:8080**. Repetir `iniciar-todo.ps1` es seguro (idempotente, no duplica).

## 3. Etapas → scripts → evidencias
| Etapa | Qué hacer | Comando | Guardar en |
|---|---|---|---|
| E1 Diseño | Dibujar diagrama con íconos AWS (ver `docs/arquitectura.md`) y explicarlo | – | `evidencias/E1` |
| E2 RDS+DynamoDB | Crear y cargar; probar restricciones | `.\02-aprovisionar.ps1` + comandos de la sección 4 | `evidencias/E2` |
| E3 S3+Lambda | Invocar Lambda, listar, get-object, dimensiones | sección 5 | `evidencias/E3` |
| E4 API | Reporte de todos los endpoints | `.\05-pruebas-api.ps1` (genera `evidencias/E4/reporte.txt`) | `evidencias/E4` |
| E5 Frontend | Registrar desde el formulario, capturas, 20 productos | http://localhost:8080 | `evidencias/E5` |
| E6 ECR | push / describe-images / pull / run | `.\06-ecr.ps1` | `evidencias/E6` |
| E7 EKS | pods, escalar 1→3, borrar pod, persistencia | `.\07-eks.ps1` + sección 7 | `evidencias/E7` |

## 4. Comandos de verificación E2 (RDS y DynamoDB)
```powershell
# Filas por estado y restricciones (SQL directo al contenedor RDS de FLOCI)
docker ps --filter "ancestor=postgres:16-alpine" --format "{{.Names}}"    # anote el nombre
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
```
(La API descubre el endpoint de RDS vía `describe-db-instances`; el usuario/clave son `lomax` / `lomax12345`.)
La carga inicial es repetible: `.\04-cargar-datos.ps1` y `schema.sql` no duplican.

## 5. Comandos de verificación E3 (S3 + Lambda)
```powershell
.\aws.ps1 s3 ls
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
.\aws.ps1 dynamodb get-item --table-name producto_atributos --key '{\"producto_id\":{\"S\":\"1\"}}'
# Repetir invocación: no debe haber objetos nuevos (clave determinista miniaturas/<id>.jpg)
```
Nota: las fotos de prueba del seed son de **1200×800** → miniatura **300×200**. Para el archivo inválido use el endpoint (`E4`) o suba un `.jpg` corrupto; queda `estado_procesamiento = ERROR`, sin miniatura y el producto sigue PENDIENTE.

## 6. Cómo llevarlo a la universidad (IMPORTANTE)
1. **En casa, con internet y con todo funcionando:** `.\offline-1-guardar-imagenes.ps1` → crea `imagenes-offline\todas.tar` (varios GB).
2. Copie **toda la carpeta `lomax` (incluida `imagenes-offline`)** a un USB / nube.
3. **En la universidad:** instale/abra Docker Desktop, luego `.\offline-2-cargar-imagenes.ps1` y `.\iniciar-todo.ps1`.
4. Si allá Docker/WSL2 no está disponible o los puertos están bloqueados, **avise al docente con anticipación**: el proyecto necesita el socket de Docker (Floci lanza RDS, Lambda y k3s como contenedores).
5. Llegue con 30–40 min de anticipación: la 1.ª subida (RDS + Lambda + 20 productos) tarda varios minutos.

## 7. Escalamiento, autorrecuperación y persistencia (E7)
```powershell
.\kubectl.ps1 -n lomax get pods -o wide
.\kubectl.ps1 -n lomax get pod -l app=backend -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IMAGEN:.spec.containers[0].image
.\kubectl.ps1 -n lomax scale deployment backend --replicas=3
.\kubectl.ps1 -n lomax get pods -w
# solicitudes por pod: cada respuesta trae el header X-Instance-Id (nombre del pod) y cada pod registra sus logs
1..12 | % { (Invoke-WebRequest -UseBasicParsing http://localhost:8081/api/instancia).Content }
.\kubectl.ps1 -n lomax logs -l app=backend --prefix --tail=5
# Autorrecuperación: anote UID, borre un pod, compare UID del reemplazo
.\kubectl.ps1 -n lomax delete pod <nombre-pod-backend>
.\kubectl.ps1 -n lomax rollout restart deployment backend      # recrear pods y comprobar que los productos siguen
```
El acceso a la app en EKS es `.\kubectl.ps1 -n lomax port-forward svc/proxy 8081:80` (deje esa ventana abierta) → http://localhost:8081.

## 8. Solución de problemas
| Síntoma | Qué hacer |
|---|---|
| `docker` no responde | Abrir Docker Desktop, esperar “Engine running”. |
| `provision.py` se queda en “esperando conexión” a RDS | `docker compose logs floci` y `docker ps -a`; comprobar que existe el contenedor `postgres:16-alpine` y que el endpoint impreso usa host `floci`. |
| Lambda falla al primer uso | Tarda: descarga `public.ecr.aws/lambda/python:3.12`. Use el modo offline. |
| 502 con `paso: lambda` | `docker compose logs floci`; la red de Lambda debe ser `lomax-net` (ver `FLOCI_SERVICES_LAMBDA_DOCKER_NETWORK`). |
| 503 con `paso: rds` | RDS aún arrancando o endpoint cambió: reiniciar API `docker compose restart backend`. |
| Pods de EKS no descargan imagen | Ver referencia en `k8s\imagenes.env`; comprobar conectividad del k3s al registro (documentar en E6). |
| Empezar de cero | `docker compose down -v` y borrar contenedores `floci-*`; volver a `iniciar-todo.ps1`. |

## 9. Estructura
`backend/` API + Dockerfile · `frontend/` 3 vistas · `proxy/` nginx · `lambda/` función + zip precompilado · `db/schema.sql` modelo · `scripts/` aprovisionamiento, carga y pruebas · `k8s/` manifiestos · `docs/` síntesis conceptual, arquitectura, defensa, equipo · `evidencias/E1..E7`.

**Aviso de honestidad técnica:** el backend y la Lambda fueron probados contra PostgreSQL real con S3/DynamoDB simulados (0 fallos en 29 comprobaciones: validaciones, 409/413/415, idempotencia, 300×200). La integración con FLOCI real (RDS/Lambda/ECR/EKS en contenedores) debe validarse en su PC antes de la defensa siguiendo esta guía.
