"""Aprovisiona (idempotente) en FLOCI: buckets S3, tabla DynamoDB, instancia RDS PostgreSQL, esquema SQL y Lambda."""
import os
import socket
import sys
import time

import boto3
import sqlalchemy as sa
from botocore.config import Config
from botocore.exceptions import ClientError

EP = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
kw = dict(endpoint_url=EP, region_name="us-east-1", aws_access_key_id="test", aws_secret_access_key="test",
          config=Config(s3={"addressing_style": "path"}))
B_ORIG, B_MINI = os.getenv("BUCKET_ORIGINALES", "lomax-originales"), os.getenv("BUCKET_MINIATURAS", "lomax-miniaturas")
TABLE, LAMBDA = os.getenv("DYNAMO_TABLE", "producto_atributos"), os.getenv("LAMBDA_NAME", "lomax-miniatura")
RDS_ID, DB_USER = os.getenv("RDS_INSTANCE_ID", "lomax-db"), os.getenv("DB_USER", "lomax")
DB_PASSWORD, DB_NAME = os.getenv("DB_PASSWORD", "lomax12345"), os.getenv("DB_NAME", "lomax")
ZIP = os.getenv("LAMBDA_ZIP", "/work/lambda/lambda_thumbnail.zip")
SCHEMA = os.getenv("SCHEMA_SQL", "/work/db/schema.sql")


def paso(t):
    print(f"\n== {t}", flush=True)


def buckets():
    paso("S3: buckets")
    s3 = boto3.client("s3", **kw)
    for b in (B_ORIG, B_MINI):
        try:
            s3.head_bucket(Bucket=b)
            print(f"  existe {b}")
        except ClientError:
            s3.create_bucket(Bucket=b)
            print(f"  creado {b}")


def dynamo():
    paso("DynamoDB: tabla")
    d = boto3.client("dynamodb", **kw)
    if TABLE in d.list_tables()["TableNames"]:
        print(f"  existe {TABLE}")
        return
    d.create_table(TableName=TABLE, AttributeDefinitions=[{"AttributeName": "producto_id", "AttributeType": "S"}],
                   KeySchema=[{"AttributeName": "producto_id", "KeyType": "HASH"}], BillingMode="PAY_PER_REQUEST")
    print(f"  creada {TABLE}")


def rds_db():
    paso("RDS: instancia PostgreSQL")
    r = boto3.client("rds", **kw)
    try:
        inst = r.describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]
        print("  existe", RDS_ID)
    except ClientError:
        r.create_db_instance(DBInstanceIdentifier=RDS_ID, DBInstanceClass="db.t3.micro", Engine="postgres",
                             MasterUsername=DB_USER, MasterUserPassword=DB_PASSWORD, DBName=DB_NAME, AllocatedStorage=20)
        print("  creada", RDS_ID)
    for _ in range(120):
        inst = r.describe_db_instances(DBInstanceIdentifier=RDS_ID)["DBInstances"][0]
        ep = inst.get("Endpoint") or {}
        print(f"  estado={inst.get('DBInstanceStatus')} endpoint={ep.get('Address')}:{ep.get('Port')}", flush=True)
        if inst.get("DBInstanceStatus") == "available" and ep.get("Address"):
            break
        time.sleep(3)
    else:
        sys.exit("RDS no llegó a 'available'")
    url = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{ep['Address']}:{ep['Port']}/{DB_NAME}"
    for i in range(60):
        try:
            with sa.create_engine(url).connect() as c:
                c.execute(sa.text("SELECT 1"))
            break
        except Exception as e:  # noqa: BLE001
            print(f"  esperando conexión ({i}): {str(e)[:80]}", flush=True)
            time.sleep(3)
    else:
        sys.exit("No se pudo conectar a RDS")
    paso("RDS: esquema y categorías")
    with sa.create_engine(url).begin() as c:
        c.exec_driver_sql(open(SCHEMA, encoding="utf-8").read())
    with sa.create_engine(url).connect() as c:
        print("  categorías:", [tuple(x) for x in c.execute(sa.text("SELECT * FROM categorias ORDER BY 1"))])


def lambda_fn():
    paso("Lambda: función de miniaturas")
    lam = boto3.client("lambda", **kw)
    code = open(ZIP, "rb").read()
    env = {"Variables": {"FLOCI_ENDPOINT": "http://floci:4566", "DYNAMO_TABLE": TABLE, "BUCKET_MINIATURAS": B_MINI}}
    try:
        lam.get_function(FunctionName=LAMBDA)
        lam.update_function_code(FunctionName=LAMBDA, ZipFile=code)
        time.sleep(1)
        lam.update_function_configuration(FunctionName=LAMBDA, Environment=env, Timeout=60, MemorySize=256)
        print("  actualizada")
    except ClientError:
        lam.create_function(FunctionName=LAMBDA, Runtime="python3.12", Role="arn:aws:iam::000000000000:role/lambda-role",
                            Handler="handler.handler", Code={"ZipFile": code}, Timeout=60, MemorySize=256, Environment=env)
        print("  creada")


if __name__ == "__main__":
    buckets()
    dynamo()
    rds_db()
    lambda_fn()
    print("\nAprovisionamiento completo.")
