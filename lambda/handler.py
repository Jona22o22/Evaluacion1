"""Lambda: valida imagen JPEG/PNG y genera miniatura <=300x300 (proporcional).
Entrada: {"producto_id","bucket","key","bucket_miniaturas"(opcional)}"""
import io
import os

import boto3
from botocore.config import Config
from PIL import Image, ImageOps

ENDPOINT = os.environ.get("FLOCI_ENDPOINT") or os.environ.get("AWS_ENDPOINT_URL")
TABLE = os.environ.get("DYNAMO_TABLE", "producto_atributos")
DEFAULT_DEST = os.environ.get("BUCKET_MINIATURAS", "lomax-miniaturas")
MAX_BYTES = 5 * 1024 * 1024
_cfg = Config(s3={"addressing_style": "path"})


def _kw():
    kw = dict(config=_cfg)
    if ENDPOINT:
        kw.update(endpoint_url=ENDPOINT, region_name=os.environ.get("AWS_REGION", "us-east-1"),
                  aws_access_key_id="test", aws_secret_access_key="test")
    return kw


def handler(event, context=None):
    s3 = boto3.client("s3", **_kw())
    tabla = boto3.resource("dynamodb", **_kw()).Table(TABLE)
    pid = str(event["producto_id"])
    bucket, key = event["bucket"], event["key"]
    dest = event.get("bucket_miniaturas") or DEFAULT_DEST
    thumb_key = f"miniaturas/{pid}.jpg"  # clave determinista: repetir no crea objetos extra
    try:
        data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        if len(data) > MAX_BYTES:
            raise ValueError("archivo mayor a 5 MB")
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG"):
            raise ValueError(f"formato no permitido: {img.format}")
        ancho_o, alto_o = img.size
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            fondo = Image.new("RGB", img.size, (255, 255, 255))
            fondo.paste(img, mask=img.split()[-1])
            img = fondo
        img = img.convert("RGB")
        img.thumbnail((300, 300), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        s3.put_object(Bucket=dest, Key=thumb_key, Body=buf.getvalue(), ContentType="image/jpeg")
        tabla.update_item(Key={"producto_id": pid},
                          UpdateExpression="SET miniatura_key=:k, estado_procesamiento=:e REMOVE error_detalle",
                          ExpressionAttributeValues={":k": thumb_key, ":e": "LISTA"})
        return {"ok": True, "estado": "LISTA", "producto_id": pid, "miniatura_key": thumb_key,
                "original": [ancho_o, alto_o], "miniatura": list(img.size)}
    except Exception as e:  # noqa: BLE001
        try:
            s3.delete_object(Bucket=dest, Key=thumb_key)
        except Exception:  # noqa: BLE001
            pass
        try:
            tabla.update_item(Key={"producto_id": pid},
                              UpdateExpression="SET estado_procesamiento=:e, error_detalle=:d REMOVE miniatura_key",
                              ExpressionAttributeValues={":e": "ERROR", ":d": str(e)[:200]})
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "estado": "ERROR", "producto_id": pid, "error": str(e)[:200]}
