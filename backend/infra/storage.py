import os
import uuid
import json
from datetime import datetime

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import UploadFile

from ..config import S3_CLIENT, BUCKET_NAME
from .messaging import kafka_producer

load_dotenv()
env = os.getenv

class S3:
    @staticmethod
    def _generate_s3_key(user_id: int, filename: str) -> str:
        file_extension = os.path.splitext(filename)[1].lower()
        unique_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())

        return f"{user_id}/snap/{timestamp}_{unique_id}{file_extension}"

    @classmethod
    async def upload_snap(cls, user_id: int, img_file: UploadFile) -> tuple[str, str] | bool:
        try:
            file_extension = os.path.splitext(img_file.filename)[1].lower()
            
            if file_extension not in [".jpg", ".jpeg", ".png", ".gif"]:
                return False
                
            s3_key = cls._generate_s3_key(user_id, img_file.filename)
            img_content = await img_file.read()
            
            S3_CLIENT.put_object(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Body=img_content,
                ContentType=img_file.content_type,
                ACL='public-read',
            )
            
            return f"https://{BUCKET_NAME}.s3.{env("AWS_S3_REGION")}.amazonaws.com/{s3_key}", s3_key
        
        except ClientError:
            return False
        
    @staticmethod
    def read_snaps(user_id: int, most_recent: bool = False) -> list[dict[str, str | datetime]] | bool:
        try:
            response = S3_CLIENT.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{user_id}/snap/")
            
            if "Contents" not in response:
                return False
            
            if most_recent:
                obj = response["Contents"][0]
                
                return {
                    "img_url": f"https://{BUCKET_NAME}.s3.{env("AWS_S3_REGION")}.amazonaws.com/{obj["Key"]}",
                    "created_at": obj["LastModified"],
                    "file_size": obj["Size"],
                    "s3_key": obj["Key"],
                }
            
            snaps = [
                {
                    "img_url": f"https://{BUCKET_NAME}.s3.{env("AWS_S3_REGION")}.amazonaws.com/{obj["Key"]}",
                    "created_at": obj["LastModified"],
                    "file_size": obj["Size"],
                    "s3_key": obj["Key"],
                }
                for obj in response["Contents"]
            ]
            
            return sorted(snaps, key=lambda x: x["created_at"], reverse=True)
        
        except ClientError:
            return False

    @staticmethod
    def delete_snap(s3_key: str) -> bool:
        try:
            message = {
                "operation": "delete_snap",
                "s3_key": s3_key,
            }

            kafka_producer.produce(
                topic="s3.delete_snap",
                value=json.dumps(message).encode("utf-8"),
            )
            
            kafka_producer.flush()
            return True

        except ClientError:
            return False
