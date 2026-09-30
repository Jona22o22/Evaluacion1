"""API de catálogo Lomax SA: Flask + RDS (PostgreSQL) + DynamoDB + S3 + Lambda (todo vía FLOCI)."""
import json
import logging
import os
import socket
from decimal import Decimal, InvalidOperation

import boto3
import sqlalchemy as sa
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, Response, jsonify, request
from flask.json.provider import DefaultJSONProvider
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://floci:4566")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
KEY = os.getenv("AWS_ACCESS_KEY_ID", "test")
SECRET = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
BUCKET_ORIG = os.getenv("BUCKET_ORIGINALES", "lomax-originales")
BUCKET_MINI = os.getenv("BUCKET_MINIATURAS", "lomax-miniaturas")
TABLE = os.getenv("DYNAMO_TABLE", "producto_atributos")
LAMBDA_NAME = os.getenv("LAMBDA_NAME", "lomax-miniatura")
RDS_ID = os.getenv("RDS_INSTANCE_ID", "lomax-db")
DB_USER = os.getenv("DB_USER", "lomax")
DB_PASSWORD = os.getenv("DB_PASSWORD", "lomax12345")
DB_NAME = os.getenv("DB_NAME", "lomax")
MAX_BYTES = 5 * 1024 * 1024
INSTANCE = os.getenv("HOSTNAME", socket.gethostname())

# Atributos obligatorios según categoría (atributos variables guardados en DynamoDB)
REQUERIDOS = {
    "Teclados": ["conexion", "distribucion"],
    "Pantallas": ["pulgadas", "resolucion"],
    "Televisores": ["pulgadas", "resolucion"],
}


class Json(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = Json(app)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("lomax")


class ApiError(Exception):
    def __init__(self, status, mensaje, paso=None, **extra):
        self.status, self.mensaje, self.paso, self.extra = status, mensaje, paso, extra


@app.errorhandler(ApiError)
def _api_error(e):
    return jsonify({"error": e.mensaje, "paso": e.paso, **e.extra}), e.status


@app.errorhandler(413)
def _too_big(_):
    return jsonify({"error": "Archivo mayor a 5 MB", "paso": "validacion"}), 413


@app.errorhandler(404)
def _nf(_):
    return jsonify({"error": "Ruta no encontrada", "paso": "ruta"}), 404


@app.after_request
def _after(resp):
    resp.headers["X-Instance-Id"] = INSTANCE
    log.info("instancia=%s %s %s -> %s", INSTANCE, request.method, request.path, resp.status_code)
    return resp


# ------------------------------------------------------------ clientes AWS
_cfg = Config(s3={"addressing_style": "path"}, retries={"max_attempts": 2}, connect_timeout=5, read_timeout=90)


def _kw():
    return dict(endpoint_url=ENDPOINT, region_name=REGION, aws_access_key_id=KEY,
                aws_secret_access_key=SECRET, config=_cfg)


def s3():
    return boto3.client("s3", **_kw())


def lam():
    return boto3.client("lambda", **_kw())


def rds():
    return boto3.client("rds", **_kw())


def tabla():
    return boto3.resource("dynamodb", **_kw()).Table(TABLE)


_engine = None


def engine():
    global _engine
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url:  # descubre el endpoint de RDS en FLOCI
            d = rds().describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]
            ep = d["Endpoint"]
            url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{ep['Address']}:{ep['Port']}/{DB_NAME}"
        args = {"connect_timeout": 5} if url.startswith("postgresql") else {}
        _engine = sa.create_engine(url, pool_pre_ping=True, connect_args=args)
    return _engine


def reset_engine():
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def db(fn):
    """Ejecuta fn(conn) en una transacción; errores de infraestructura -> 503 (paso rds)."""
    try:
        with engine().begin() as conn:
            return fn(conn)
    except IntegrityError:
        raise
    except (OperationalError, DBAPIError, ClientError, BotoCoreError) as e:
        reset_engine()
        raise ApiError(503, f"RDS no disponible: {e.__class__.__name__}", "rds")


# ------------------------------------------------------------ utilidades
def producto_row(conn, pid):
    r = conn.execute(sa.text(
        "SELECT p.producto_id,p.codigo,p.nombre,p.descripcion,p.precio,p.categoria_id,c.nombre AS categoria,"
        "p.fecha_registro,p.estado FROM productos p JOIN categorias c USING(categoria_id) "
        "WHERE p.producto_id=:i"), {"i": pid}).mappings().first()
    return dict(r) if r else None


def obtener_producto(pid):
    p = db(lambda c: producto_row(c, pid))
    if not p:
        raise ApiError(404, f"Producto {pid} no existe", "rds")
    p["fecha_registro"] = p["fecha_registro"].isoformat()
    return p


def dynamo_get(pid):
    try:
        return tabla().get_item(Key={"producto_id": str(pid)}).get("Item")
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, f"DynamoDB falló: {e.__class__.__name__}", "dynamodb", producto_id=pid)


def parse_json():
    try:
        d = json.loads(request.get_data() or b"{}", parse_float=Decimal)
    except ValueError:
        raise ApiError(400, "JSON inválido", "validacion")
    if not isinstance(d, dict):
        raise ApiError(400, "Se esperaba un objeto JSON", "validacion")
    return d


def validar_atributos(nombre_cat, attrs):
    if not isinstance(attrs, dict) or not attrs:
        raise ApiError(400, "atributos debe ser un objeto no vacío", "validacion")
    faltan = [k for k in REQUERIDOS.get(nombre_cat, []) if str(attrs.get(k, "")).strip() == ""]
    if faltan:
        raise ApiError(400, f"Faltan atributos obligatorios para {nombre_cat}: {', '.join(faltan)}", "validacion")
    return {str(k): (v if isinstance(v, (int, Decimal)) and not isinstance(v, bool) else str(v)) for k, v in attrs.items()}


def detectar_tipo(b):
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    return None, None


# ------------------------------------------------------------ endpoints
@app.get("/salud")
def salud():
    return jsonify({"estado": "ok", "instancia": INSTANCE})


@app.get("/instancia")
def instancia():
    return jsonify({"instancia": INSTANCE})


@app.get("/categorias")
def categorias():
    rows = db(lambda c: c.execute(sa.text("SELECT categoria_id,nombre FROM categorias ORDER BY categoria_id")).mappings().all())
    return jsonify([dict(r) for r in rows])


@app.post("/productos")
def crear_producto():
    d = parse_json()
    for campo in ("codigo", "nombre", "descripcion"):
        if not isinstance(d.get(campo), str) or not d[campo].strip():
            raise ApiError(400, f"Campo obligatorio: {campo}", "validacion")
    try:
        precio = Decimal(str(d.get("precio")))
        if not precio.is_finite() or precio < 0:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise ApiError(400, "precio debe ser un número mayor o igual a 0", "validacion")
    if isinstance(d.get("categoria_id"), bool) or not isinstance(d.get("categoria_id"), int):
        raise ApiError(400, "categoria_id debe ser un entero", "validacion")
    cat = db(lambda c: c.execute(sa.text("SELECT nombre FROM categorias WHERE categoria_id=:i"),
                                 {"i": d["categoria_id"]}).scalar())
    if cat is None:
        raise ApiError(400, "La categoría no existe", "validacion")
    attrs = validar_atributos(cat, d.get("atributos"))

    def ins(c):
        return c.execute(sa.text(
            "INSERT INTO productos(codigo,nombre,descripcion,precio,categoria_id,estado) "
            "VALUES(:c,:n,:d,:p,:k,'PENDIENTE') RETURNING producto_id"),
            {"c": d["codigo"].strip(), "n": d["nombre"].strip(), "d": d["descripcion"].strip(),
             "p": precio, "k": d["categoria_id"]}).scalar()
    try:
        pid = db(ins)
    except IntegrityError as e:
        code = getattr(e.orig, "pgcode", None)
        if code == "23505":
            ex = db(lambda c: c.execute(sa.text("SELECT producto_id,estado FROM productos WHERE codigo=:c"),
                                        {"c": d["codigo"].strip()}).mappings().first())
            raise ApiError(409, "Código de producto duplicado", "rds",
                           producto_id=ex["producto_id"] if ex else None, estado=ex["estado"] if ex else None)
        raise ApiError(400, "Datos rechazados por RDS", "rds")
    try:
        tabla().put_item(Item={"producto_id": str(pid), "atributos": attrs, "estado_procesamiento": "PENDIENTE"})
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, f"DynamoDB falló ({e.__class__.__name__}). Producto queda PENDIENTE; "
                            f"complete con PUT /productos/{pid}/atributos", "dynamodb", producto_id=pid, estado="PENDIENTE")
    return jsonify({"producto_id": pid, "estado": "PENDIENTE"}), 201


@app.put("/productos/<int:pid>/atributos")
def completar_atributos(pid):
    p = obtener_producto(pid)
    attrs = validar_atributos(p["categoria"], parse_json().get("atributos"))
    try:
        tabla().update_item(Key={"producto_id": str(pid)},
                            UpdateExpression="SET atributos=:a, estado_procesamiento=if_not_exists(estado_procesamiento,:e)",
                            ExpressionAttributeValues={":a": attrs, ":e": "PENDIENTE"})
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, f"DynamoDB falló: {e.__class__.__name__}", "dynamodb", producto_id=pid)
    return jsonify({"producto_id": pid, "estado": p["estado"], "atributos": attrs})


def procesar(pid, p):
    """Invoca Lambda (síncrona); publica solo si atributos y miniatura están confirmados."""
    item = dynamo_get(pid)
    if not item or not item.get("imagen_original_key"):
        raise ApiError(409, "No existe imagen original para este producto", "s3", producto_id=pid, estado=p["estado"])
    if not item.get("atributos"):
        raise ApiError(409, "Faltan atributos en DynamoDB (use PUT /productos/{id}/atributos)", "dynamodb",
                       producto_id=pid, estado=p["estado"])
    try:
        s3().head_object(Bucket=BUCKET_ORIG, Key=item["imagen_original_key"])
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            raise ApiError(409, "El original ya no existe en S3", "s3", producto_id=pid, estado=p["estado"])
        raise ApiError(502, "S3 falló al verificar el original", "s3", producto_id=pid, estado=p["estado"])
    except BotoCoreError:
        raise ApiError(502, "S3 no disponible", "s3", producto_id=pid, estado=p["estado"])
    payload = {"producto_id": str(pid), "bucket": BUCKET_ORIG, "key": item["imagen_original_key"],
               "bucket_miniaturas": BUCKET_MINI}
    try:
        r = lam().invoke(FunctionName=LAMBDA_NAME, InvocationType="RequestResponse", Payload=json.dumps(payload).encode())
        out = json.loads(r["Payload"].read() or b"{}")
    except (ClientError, BotoCoreError, ValueError) as e:
        raise ApiError(502, f"Lambda no disponible: {e.__class__.__name__}", "lambda", producto_id=pid, estado="PENDIENTE")
    if r.get("FunctionError"):
        raise ApiError(502, "La función Lambda reportó un error de ejecución", "lambda", producto_id=pid,
                       estado="PENDIENTE", detalle=out)
    if not out.get("ok"):
        raise ApiError(400, f"Imagen inválida: {out.get('error')}", "lambda", producto_id=pid,
                       estado="PENDIENTE", estado_procesamiento="ERROR")
    item = dynamo_get(pid)
    if not item or item.get("estado_procesamiento") != "LISTA" or not item.get("miniatura_key") or not item.get("atributos"):
        raise ApiError(502, "Lambda respondió OK pero DynamoDB no confirma miniatura/atributos", "dynamodb",
                       producto_id=pid, estado="PENDIENTE")
    try:
        s3().head_object(Bucket=BUCKET_MINI, Key=item["miniatura_key"])
    except (ClientError, BotoCoreError):
        raise ApiError(502, "La miniatura no está disponible en S3", "s3", producto_id=pid, estado="PENDIENTE")
    db(lambda c: c.execute(sa.text("UPDATE productos SET estado='PUBLICADO' WHERE producto_id=:i"), {"i": pid}))
    return jsonify({"producto_id": pid, "estado": "PUBLICADO", "miniatura_key": item["miniatura_key"],
                    "estado_procesamiento": "LISTA"})


@app.post("/productos/<int:pid>/imagen")
def subir_imagen(pid):
    p = obtener_producto(pid)
    f = request.files.get("imagen") or request.files.get("file")
    data = f.read() if f else request.get_data()
    if not data:
        raise ApiError(400, "Falta el archivo (campo 'imagen')", "validacion")
    if len(data) > MAX_BYTES:
        raise ApiError(413, "Archivo mayor a 5 MB", "validacion")
    ctype, ext = detectar_tipo(data)
    if not ctype:
        raise ApiError(415, "Formato no permitido: solo JPEG o PNG", "validacion")
    key = f"originales/{pid}.{ext}"
    try:
        s3().put_object(Bucket=BUCKET_ORIG, Key=key, Body=data, ContentType=ctype)
        tabla().update_item(Key={"producto_id": str(pid)},
                            UpdateExpression="SET imagen_original_key=:k, estado_procesamiento=:e",
                            ExpressionAttributeValues={":k": key, ":e": "PENDIENTE"})
    except (ClientError, BotoCoreError) as e:
        raise ApiError(502, f"No se pudo guardar el original: {e.__class__.__name__}", "s3", producto_id=pid, estado=p["estado"])
    return procesar(pid, p)


@app.post("/productos/<int:pid>/reprocesar")
def reprocesar(pid):
    return procesar(pid, obtener_producto(pid))


def armar(p, item):
    item = item or {}
    p["atributos"] = item.get("atributos", {})
    p["imagen_original_key"] = item.get("imagen_original_key")
    p["miniatura_key"] = item.get("miniatura_key")
    p["estado_procesamiento"] = item.get("estado_procesamiento")
    p["miniatura_url"] = f"/api/productos/{p['producto_id']}/imagen" if item.get("miniatura_key") else None
    return p


@app.get("/productos")
def listar():
    rows = db(lambda c: c.execute(sa.text(
        "SELECT p.producto_id,p.codigo,p.nombre,p.descripcion,p.precio,p.categoria_id,c.nombre AS categoria,"
        "p.fecha_registro,p.estado FROM productos p JOIN categorias c USING(categoria_id) "
        "WHERE p.estado='PUBLICADO' ORDER BY p.producto_id")).mappings().all())
    out = []
    for r in rows:
        p = dict(r)
        p["fecha_registro"] = p["fecha_registro"].isoformat()
        out.append(armar(p, dynamo_get(p["producto_id"])))
    return jsonify(out)


@app.get("/productos/<int:pid>")
def detalle(pid):
    return jsonify(armar(obtener_producto(pid), dynamo_get(pid)))


@app.get("/productos/<int:pid>/imagen")
def imagen(pid):
    item = dynamo_get(pid)
    if not item or item.get("estado_procesamiento") != "LISTA" or not item.get("miniatura_key"):
        raise ApiError(404, "Miniatura no disponible", "dynamodb")
    try:
        o = s3().get_object(Bucket=BUCKET_MINI, Key=item["miniatura_key"])
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            raise ApiError(404, "Miniatura no disponible", "s3")
        raise ApiError(502, "S3 falló", "s3")
    except BotoCoreError:
        raise ApiError(502, "S3 no disponible", "s3")
    return Response(o["Body"].read(), mimetype=o.get("ContentType", "image/jpeg"),
                    headers={"Cache-Control": "public, max-age=60"})
