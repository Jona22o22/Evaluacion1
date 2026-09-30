"""E4: ejecuta todos los endpoints y verifica directamente RDS, DynamoDB y S3. Guarda reporte en evidencias/E4/reporte.txt"""
import io
import os
import time

import boto3
import requests
import sqlalchemy as sa
from botocore.config import Config
from PIL import Image

API = os.getenv("API_URL", "http://proxy/api")
EP = os.getenv("AWS_ENDPOINT_URL", "http://floci:4566")
kw = dict(endpoint_url=EP, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test", config=Config(s3={"addressing_style": "path"}))
lineas, fallos = [], 0


def log(t):
    print(t, flush=True)
    lineas.append(t)


def check(nombre, cond, detalle=""):
    global fallos
    fallos += 0 if cond else 1
    log(f"[{'OK' if cond else 'FALLO'}] {nombre} {detalle}")


def jpg(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (30, 120, 200)).save(b, "JPEG")
    return b.getvalue()


ri = boto3.client("rds", **kw).describe_db_instances(DBInstanceIdentifier="lomax-db")["DBInstances"][0]["Endpoint"]
eng = sa.create_engine(f"postgresql+psycopg2://lomax:lomax12345@{ri['Address']}:{ri['Port']}/lomax")
tabla = boto3.resource("dynamodb", **kw).Table("producto_atributos")
s3 = boto3.client("s3", **kw)
cod = f"E4-{int(time.time())}"
base = {"codigo": cod, "nombre": "Producto prueba E4", "descripcion": "Prueba", "precio": 99.9, "categoria_id": 1,
        "atributos": {"conexion": "USB", "distribucion": "ES"}}

r = requests.get(f"{API}/categorias"); check("GET /categorias 200", r.status_code == 200 and len(r.json()) >= 3, r.text[:100])
r = requests.post(f"{API}/productos", json=base); check("POST /productos 201 PENDIENTE", r.status_code == 201, r.text)
pid = r.json()["producto_id"]
with eng.connect() as c:
    est = c.execute(sa.text("select estado from productos where producto_id=:i"), {"i": pid}).scalar()
check("RDS: fila PENDIENTE", est == "PENDIENTE", est)
it = tabla.get_item(Key={"producto_id": str(pid)}).get("Item")
check("DynamoDB: atributos guardados", bool(it) and it["atributos"]["conexion"] == "USB", str(it))
r = requests.post(f"{API}/productos", json=base); check("POST duplicado 409", r.status_code == 409, r.text)
r = requests.post(f"{API}/productos", json={**base, "codigo": cod + "a", "precio": -5}); check("precio negativo 400", r.status_code == 400, r.text)
r = requests.post(f"{API}/productos", json={**base, "codigo": cod + "b", "categoria_id": 999}); check("categoría inexistente 400", r.status_code == 400, r.text)
r = requests.get(f"{API}/productos/{pid}"); check("GET /productos/{id} 200 PENDIENTE", r.status_code == 200 and r.json()["estado"] == "PENDIENTE")
r = requests.get(f"{API}/productos/99999999"); check("GET /productos/{id} inexistente 404", r.status_code == 404)
r = requests.post(f"{API}/productos/{pid}/reprocesar"); check("reprocesar sin original 409", r.status_code == 409, r.text)
r = requests.get(f"{API}/productos/{pid}/imagen"); check("GET imagen sin miniatura 404", r.status_code == 404)
r = requests.post(f"{API}/productos/{pid}/imagen", files={"imagen": ("a.txt", b"hola", "text/plain")}); check("archivo no imagen 415", r.status_code == 415, r.text)
r = requests.post(f"{API}/productos/{pid}/imagen", files={"imagen": ("g.jpg", b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 1), "image/jpeg")}); check("archivo >5MB 413", r.status_code == 413, r.text)
r = requests.post(f"{API}/productos/{pid}/imagen", files={"imagen": ("x.jpg", b"\xff\xd8\xff basura", "image/jpeg")}); check("JPEG corrupto 400 (paso lambda)", r.status_code == 400 and r.json().get("paso") == "lambda", r.text)
with eng.connect() as c:
    est = c.execute(sa.text("select estado from productos where producto_id=:i"), {"i": pid}).scalar()
check("Sigue PENDIENTE tras imagen inválida", est == "PENDIENTE", est)
lst = requests.get(f"{API}/productos").json(); check("PENDIENTE no aparece en catálogo", all(p["producto_id"] != pid for p in lst))
r = requests.post(f"{API}/productos/{pid}/imagen", files={"imagen": ("ok.jpg", jpg(1200, 800), "image/jpeg")}); check("POST imagen válida 200 PUBLICADO", r.status_code == 200 and r.json()["estado"] == "PUBLICADO", r.text)
with eng.connect() as c:
    est = c.execute(sa.text("select estado from productos where producto_id=:i"), {"i": pid}).scalar()
check("RDS: fila PUBLICADO", est == "PUBLICADO", est)
it = tabla.get_item(Key={"producto_id": str(pid)})["Item"]
check("DynamoDB: estado LISTA + miniatura_key", it["estado_procesamiento"] == "LISTA" and it["miniatura_key"] == f"miniaturas/{pid}.jpg", str(it))
antes = sorted(o["Key"] for o in s3.list_objects_v2(Bucket="lomax-miniaturas", Prefix="miniaturas/").get("Contents", []))
r = requests.post(f"{API}/productos/{pid}/reprocesar"); check("reprocesar 200", r.status_code == 200, r.text)
desp = sorted(o["Key"] for o in s3.list_objects_v2(Bucket="lomax-miniaturas", Prefix="miniaturas/").get("Contents", []))
check("S3: reprocesar no duplica objetos", antes == desp, f"{len(antes)} -> {len(desp)}")
r = requests.get(f"{API}/productos/{pid}/imagen"); im = Image.open(io.BytesIO(r.content))
check("GET imagen 200 image/jpeg 300x200", r.status_code == 200 and r.headers["Content-Type"] == "image/jpeg" and im.size == (300, 200), f"{im.size}")
desde_s3 = s3.get_object(Bucket="lomax-miniaturas", Key=it["miniatura_key"])["Body"].read()
check("Bytes del endpoint == bytes descargados de S3", desde_s3 == r.content)
lst = requests.get(f"{API}/productos"); check("GET /productos solo publicados e incluye el nuevo", lst.status_code == 200 and any(p["producto_id"] == pid for p in lst.json()) and all(p["estado"] == "PUBLICADO" for p in lst.json()), f"{len(lst.json())} publicados")
log(f"\nRESULTADO: {'TODO OK' if fallos == 0 else str(fallos) + ' FALLOS'}")
os.makedirs("/work/evidencias/E4", exist_ok=True)
open("/work/evidencias/E4/reporte.txt", "w", encoding="utf-8").write("\n".join(lineas) + "\n")
raise SystemExit(1 if fallos else 0)
