import os

import boto3
import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from pymongo import MongoClient

load_dotenv()
env = os.getenv

def get_rds_db_url():
    user = env("AWS_RDS_DB_USER")
    password = env("AWS_RDS_DB_PASS")
    host = env("AWS_RDS_DB_HOST")
    port = env("AWS_RDS_DB_PORT")
    db_name = env("AWS_RDS_DB_NAME")
    
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}?sslmode=require"

RDS_ENGINE = create_engine(
    get_rds_db_url(),
    poolclass=QueuePool,
    pool_size=25,
    max_overflow=50,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 10,
        "application_name": "Snapthril Backend",
    },
)

REDIS_CLIENT = redis.Redis(
    host=env("REDIS_HOST"),
    port=int(env("REDIS_PORT")),
    username="default",
    password=env("REDIS_USER_PASS"),
    ssl=True,
    ssl_cert_reqs=None,
    ssl_ca_certs=None,
    ssl_keyfile=None,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=10,
    retry_on_timeout=True,
    socket_keepalive=True,
    health_check_interval=30,
)

S3_CLIENT = boto3.client(
    "s3",
    aws_access_key_id=env("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=env("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=env("AWS_S3_REGION"),
    config=boto3.session.Config(signature_version="s3v4"),
)
BUCKET_NAME = env("AWS_S3_BUCKET_NAME")

MONGO_CLIENT = MongoClient(
    env("MONGO_CONNECTION_STRING"),
    tls=True,
    tlsAllowInvalidCertificates=False,
    socketTimeoutMS=5000,
    connectTimeoutMS=10000,
    maxPoolSize=120,
    retryWrites=True,
    retryReads=True,
)
MONGO_DB = MONGO_CLIENT[env("MONGO_DB_NAME")]
MONGO_COLLECTION = MONGO_DB.image_tags
