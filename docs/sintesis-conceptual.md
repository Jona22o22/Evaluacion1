# Producto 1 – Síntesis conceptual (Cloud, Contenedores, Kubernetes, AWS)
> Cada integrante debe **entender y poder defender** estas tablas. La última columna relaciona el concepto con lo implementado.

## Cloud Computing
| Concepto | Definición | Relación con la solución |
|---|---|---|
| Características del Cloud | Acceso bajo demanda, pago por uso, recursos agrupados (compartidos), elasticidad rápida, servicio medido. | Se crean bases, buckets y funciones con un comando/API cuando se necesitan (bajo demanda); Lambda cobra por ejecución; EKS escala réplicas 1→3 (elasticidad). |
| Escalabilidad vertical y horizontal | Vertical: más CPU/RAM al mismo servidor. Horizontal: más instancias/Pods que reparten carga. | Escalamos el backend **horizontalmente** de 1 a 3 pods con `kubectl scale`; los pods son sin estado porque los datos están en RDS/DynamoDB/S3. |
| Virtualización | Varios entornos simulados (VMs) sobre un mismo hardware físico. | Docker Desktop corre sobre WSL2/VM; FLOCI emula servicios AWS sobre nuestro PC en vez de infraestructura real. |
| IaaS, PaaS, SaaS | IaaS: infraestructura (EC2). PaaS: plataforma/servicios administrados (RDS). SaaS: software terminado (Gmail). | RDS, DynamoDB, EKS y Lambda son PaaS/administrados; el catálogo de Lomax sería un SaaS para sus vendedores. |
| Tipos de nube | Pública (AWS), privada (exclusiva), híbrida (mezcla). | Usamos un emulador local de nube **pública** AWS (FLOCI) para desarrollar sin costo. |
| Ventajas y limitaciones | Ventajas: menos costo de hardware, alta disponibilidad, escalabilidad. Limitaciones: dependencia de internet y vendor lock-in. | Datos ya no en PCs individuales (se recupera todo tras fallo); usar API AWS nos ata al proveedor, aunque FLOCI permite probar localmente. |

## Contenedores
| Concepto | Definición | Relación con la solución |
|---|---|---|
| Contenedor | Paquete ligero ejecutable con código, librerías y configuración. | Frontend, proxy y API corren cada uno en su contenedor; RDS, Lambda y EKS también los usa FLOCI. |
| Imagen y contenedor | Imagen: plantilla inmutable de solo lectura. Contenedor: instancia en ejecución. | Se construyen 3 imágenes (`lomax-*`) y se publican en ECR; los pods son contenedores de esas imágenes. |
| Dockerfile | Instrucciones para construir una imagen. | `backend/Dockerfile`, `frontend/Dockerfile`, `proxy/Dockerfile`. |
| Redes | Comunicación aislada entre contenedores. | Red `lomax-net`: el proxy alcanza `frontend` y `backend` por nombre; el backend alcanza `floci`. |
| Volúmenes | Persisten datos fuera del ciclo de vida del contenedor. | Volumen `floci-data` conserva el estado de FLOCI (DynamoDB/S3) al reiniciar. |
| Docker Compose | Define y ejecuta apps multi-contenedor con YAML. | `docker-compose.yml` levanta floci, backend, frontend y proxy con redes y variables de entorno. |
| Ventajas/limitaciones | Portabilidad y arranque rápido; comparten kernel (menos aislamiento que una VM). | El mismo proyecto corre en casa y en la universidad; Lambda/RDS de FLOCI requieren acceso al socket de Docker. |

## Kubernetes
| Concepto | Definición | Relación con la solución |
|---|---|---|
| Arquitectura básica | Control Plane (administra) + Worker Nodes (ejecutan apps). | EKS de FLOCI crea un clúster k3s con API server real. |
| Cluster | Conjunto de nodos que ejecutan contenedores administrados por Kubernetes. | Clúster `lomax-eks`. |
| Pod | Unidad mínima desplegable; uno o más contenedores con red/almacenamiento compartidos. | Cada réplica del backend es un pod (su nombre aparece en `X-Instance-Id`). |
| Deployment | Estado deseado de Pods (réplicas, actualizaciones). | `k8s/10-backend.yaml`: `replicas: 1` → escalamos a 3. |
| Service | Red estable y balanceo interno/externo para un conjunto de Pods. | `backend` (8000), `frontend` (80) y `proxy` (NodePort 30080) reparten tráfico. |
| Escalamiento | Aumentar/disminuir Pods según demanda (HPA). | `kubectl scale` a 3 réplicas y verificación de tráfico por pod. |
| Autorrecuperación | Kubernetes recrea Pods caídos para mantener las réplicas. | Borramos un pod, cambia el UID y se recupera el número de réplicas sin perder productos. |

## AWS
| Concepto | Definición | Relación con la solución |
|---|---|---|
| RDS | Base relacional administrada (SQL). | Guarda `categorias` y `productos` (código único, precio ≥ 0, FK a categoría, estado PENDIENTE/PUBLICADO). |
| DynamoDB | NoSQL clave-valor de esquema flexible. | Guarda atributos variables (teclado: conexión/distribución; pantalla: pulgadas/resolución) e info de imagen por `producto_id`. |
| S3 | Almacenamiento de objetos. | Dos buckets: originales y miniaturas. |
| Lambda | Cómputo serverless por evento. | Valida y genera miniaturas ≤ 300×300 (proporcional) y actualiza DynamoDB. |
| ECR | Registro privado de imágenes Docker. | Almacena `lomax-frontend`, `lomax-backend`, `lomax-proxy`. |
| EKS | Kubernetes administrado. | Ejecuta la app con las imágenes de ECR, escala y se autorrecupera. |

### Decisiones para la defensa
- **¿Por qué dos bases?** Datos estructurados y con restricciones → RDS; atributos que cambian según el producto → DynamoDB. La relación se verifica desde la API por `producto_id` (sin FK entre servicios).
- **¿Por qué PENDIENTE?** Solo se publica cuando hay atributos **y** miniatura confirmada; así el catálogo nunca muestra productos incompletos y se puede reintentar sin duplicar.
- **¿Por qué Lambda síncrona?** La API necesita saber el resultado para decidir la publicación en la misma solicitud.
- **¿Por qué clave determinista?** `miniaturas/{id}.jpg` hace la operación idempotente.
