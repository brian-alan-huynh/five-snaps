import os
from typing import Final

import boto3
from dotenv import load_dotenv

load_dotenv()
env = os.getenv


S3_CLIENT: Final[boto3.client] = boto3.client(
    "s3",
    aws_access_key_id=env("AWS_S3_ACCESS_KEY_ID"),
    aws_secret_access_key=env("AWS_S3_SECRET_ACCESS_KEY"),
    region_name=env("AWS_S3_REGION")
)

BUCKET_NAME: Final[str] = env("AWS_S3_BUCKET_NAME")
