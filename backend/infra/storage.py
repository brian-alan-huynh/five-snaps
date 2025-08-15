import os
import uuid
import json
from datetime import datetime

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import UploadFile

from ..config import BUCKET_NAME
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
    async def upload_snap(cls, user_id: int, file: UploadFile) -> str | bool:
        try:
            file_extension = os.path.splitext(file.filename)[1].lower()
            
            if file_extension not in [".jpg", ".jpeg", ".png", ".gif"]:
                return False
                
            s3_key = cls._generate_s3_key(user_id, file.filename)
            file_content = await file.read()
            
            message = {
                "operation": "upload_snap",
                "s3_key": s3_key,
                "file_content": file_content.hex(),
                "content_type": file.content_type,
            }
            
            kafka_producer.produce(
                topic="s3.upload_snap",
                value=json.dumps(message).encode("utf-8"),
            )
            
            kafka_producer.flush()
            
            return f"https://{BUCKET_NAME}.s3.{env('AWS_REGION')}.amazonaws.com/{s3_key}"
        
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

