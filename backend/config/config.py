import os

import boto3
import redis
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
env = os.getenv

REDIS_CLIENT = redis.Redis(
    host=env("REDIS_HOST"),
    port=int(env("REDIS_PORT")),
    username="default",
    password=env("REDIS_USER_PASS"),
    ssl=True,
    ssl_cert_reqs=None,
    ssl_ca_certs=None,
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
