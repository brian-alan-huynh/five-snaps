import os
from typing import Final

import boto3
import redis
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

# Redis
REDIS_CLIENT: Final[redis.Redis] = redis.Redis(
    host=env("REDIS_HOST"),
    port=int(env("REDIS_PORT")),
    decode_responses=True,
    username="default",
    password=env("REDIS_USER_PASS"),
)

# S3
S3_CLIENT: Final[boto3.client] = boto3.client(
    "s3",
    aws_access_key_id=env("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=env("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=env("AWS_S3_REGION")
)

BUCKET_NAME: Final[str] = env("AWS_S3_BUCKET_NAME")

# write kafka config for facebook post uploads
