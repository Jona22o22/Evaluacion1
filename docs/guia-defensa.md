# Guía rápida para la defensa (todos deben poder hacerlo)
1. **Explicar el diagrama** (`docs/arquitectura.md`).
2. **Recorrido de un producto:** POST → PENDIENTE → imagen → Lambda → PUBLICADO. Un registro incompleto (sin miniatura o sin atributos) permanece PENDIENTE y no aparece en el catálogo.
3. **Código duplicado:** en el formulario o `POST /productos` con el mismo código → **409**. Atributos variables: `.\aws.ps1 dynamodb get-item ...` (teclado vs pantalla). Persistencia: `docker restart <postgres>` y repetir consultas.
4. **Miniatura:** `s3api get-object` → dimensiones (1200×800 → 300×200) → repetir `lambda invoke` y comprobar que `s3 ls` no muestra objetos nuevos.
5. **Endpoints válidos/ inválidos:** 400 (datos), 409 (duplicado / sin original), 413 (>5 MB), 415 (no JPEG/PNG), 404, 502/503 (dependencia caída; respuesta incluye `paso`). Completar pendiente: `POST /productos/{id}/reprocesar` o `/imagen` sin crear otro producto.
6. **Dashboard:** registrar un producto y mostrar detalle; el `producto_id` y los datos vienen de la API (revisar pestaña Red del navegador).
7. **ECR:** `docker push`, digest (`ecr describe-images`), `docker pull`, `docker run` de la imagen recuperada.
8. **EKS:** `kubectl get pods -o custom-columns=...,IMAGEN:...` (imagen apunta a ECR), `scale --replicas=3`, borrar pod (cambia UID), catálogo intacto.
