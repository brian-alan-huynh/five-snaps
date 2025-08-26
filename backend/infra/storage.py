import os
import uuid
import json
from io import BytesIO
from datetime import datetime

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from fastapi import UploadFile

from messaging import kafka_producer
from backend.main import app
from backend.config.config import S3_CLIENT, BUCKET_NAME

class S3Error(Exception):
    "Exception for S3 operations"
    pass

class S3FileExtensionError(S3Error):
    "Exception for invalid S3 file extensions"
    pass

class KafkaProduceDeliveryError(S3Error):
    "Exception for Kafka producer message delivery"
    pass

class KafkaProduceOperationError(S3Error):
    "Exception for Kafka producer operations"
    pass

load_dotenv()
env = os.getenv

class S3:
    @staticmethod
    def _raise_client_operation_error(func_name: str, error: Exception) -> None:
        error_message = f"Failed to perform operation on S3 in {func_name}: {error}"
        app.state.logger.log_error(error_message)
        raise S3Error(error_message) from error
    
    @staticmethod
    def _raise_kafka_message_delivery_failure(func_name: str, remaining_messages: int) -> None:
        error_message = f"Failed to deliver message to Kafka in {func_name}: {remaining_messages} messages (within 15 seconds)"
        app.state.logger.log_error(error_message)
        raise KafkaProduceDeliveryError(error_message)
    
    @staticmethod
    def _raise_kafka_message_produce_failure(func_name: str, error: Exception) -> None:
        error_message = f"Failed to produce message to Kafka in {func_name}: {error}"
        app.state.logger.log_error(error_message)
        raise KafkaProduceOperationError(error_message) from error
    
    @staticmethod
    def _generate_s3_key(user_id: int, filename: str) -> str:
        file_extension = os.path.splitext(filename)[1].lower()
        unique_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())

        return f"{user_id}/snap/{timestamp}_{unique_id}{file_extension}"

    @classmethod
    async def upload_snap(cls, user_id: int, img_file: UploadFile) -> tuple[str, str]:
        try:
            file_extension = os.path.splitext(img_file.filename)[1].lower()
            
            if file_extension not in [".jpg", ".jpeg", ".png", ".gif"]:
                error_message = f"Invalid file extension: {file_extension}"
                
                app.state.logger.log_error(error_message)
                raise S3FileExtensionError(error_message)
                
            s3_key = cls._generate_s3_key(user_id, img_file.filename)
            img_content = BytesIO(await img_file.read())
            
            S3_CLIENT.upload_fileobj(
                Bucket=BUCKET_NAME,
                Key=s3_key,
                Fileobj=img_content,
                ExtraArgs={
                    "ContentType": img_file.content_type,
                    "ACL": "public-read",
                },
            )
            
            return f"https://{BUCKET_NAME}.s3.{env("AWS_S3_REGION")}.amazonaws.com/{s3_key}", s3_key
        
        except ClientError as e:
            cls._raise_client_operation_error("upload_snap", e)
        
    @classmethod
    def read_snaps(cls, user_id: int) -> list[dict[str, str | datetime]]:
        try:
            response = S3_CLIENT.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{user_id}/snap/")
            
            if response["KeyCount"] == 0:
                return []
            
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
        
        except ClientError as e:
            cls._raise_client_operation_error("read_snaps", e)
        
    @classmethod
    def read_newest_snap(cls, user_id: int) -> str:
        try:
            response = S3_CLIENT.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{user_id}/snap/")
            
            if response["KeyCount"] == 0:
                return ""
            
            return f"https://{BUCKET_NAME}.s3.{env("AWS_S3_REGION")}.amazonaws.com/{response["Contents"][0]["Key"]}"
        
        except ClientError as e:
            cls._raise_client_operation_error("read_newest_snap", e)
        
    @classmethod
    def get_snap_count(cls, user_id: int) -> int:
        try:
            response = S3_CLIENT.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{user_id}/snap/")
            return response["KeyCount"]
        
        except ClientError as e:
            cls._raise_client_operation_error("get_snap_count", e)

    @classmethod
    def delete_snap(cls, s3_key: str) -> None:
        try:
            message = {
                "operation": "delete_snap",
                "s3_key": s3_key,
            }

            kafka_producer.produce(
                topic="s3.delete_snap",
                key=str(s3_key).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )
            
            remaining_messages = kafka_producer.flush(timeout=15)
            
            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("delete_snap", remaining_messages)
            
            return

        except KafkaProduceDeliveryError:
            raise

        except Exception as e:
            cls._raise_kafka_message_produce_failure("delete_snap", e)
        
    @classmethod
    def delete_all_snaps(cls, user_id: int) -> None:
        try:
            message = {
                "operation": "delete_all_snaps",
                "user_id": user_id,
            }

            kafka_producer.produce(
                topic="s3.delete_all_snaps",
                key=str(user_id).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )
            
            remaining_messages = kafka_producer.flush(timeout=15)
            
            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("delete_all_snaps", remaining_messages)
            
            return

        except KafkaProduceDeliveryError:
            raise

        except Exception as e:
            cls._raise_kafka_message_produce_failure("delete_all_snaps", e)
