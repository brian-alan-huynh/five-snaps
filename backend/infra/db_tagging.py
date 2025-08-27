import json
from datetime import datetime

from messaging import kafka_producer
from backend.main import app
from backend.config.config import MONGO_COLLECTION

class MongoDBError(Exception):
    "Exception for MongoDB operations"
    pass

class KafkaProduceDeliveryError(MongoDBError):
    "Exception for Kafka producer message delivery"
    pass

class KafkaProduceOperationError(MongoDBError):
    "Exception for Kafka producer operations"
    pass

class MongoDB:
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
    
    @classmethod
    def add_img_tags(cls, user_id: int, s3_key: str, tags: list[str]) -> None:
        try:
            message = {
                "operation": "add_img_tags",
                "user_id": user_id,
                "s3_key": s3_key,
                "tags": tags,
                "caption": "",
                "created_at": datetime.now().isoformat(),
            }
            
            kafka_producer.produce(
                topic="mongodb.add_img_tags",
                key=str(user_id).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )
            
            remaining_messages = kafka_producer.flush(timeout=15)
            
            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("add_img_tags", remaining_messages)
            
            return
        
        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("add_img_tags", e)

    @classmethod
    def write_img_caption(cls, s3_key: str, caption: str) -> None:
        try:
            message = {
                "operation": "write_img_caption",
                "s3_key": s3_key,
                "caption": caption,
            }
            
            kafka_producer.produce(
                topic="mongodb.write_img_caption",
                key=str(s3_key).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )
            
            remaining_messages = kafka_producer.flush(timeout=15)
            
            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("write_img_caption", remaining_messages)
            
            return
        
        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("write_img_caption", e)

    @staticmethod
    def read_img_tags_and_captions(user_id: int) -> list[dict[str, str | datetime]]:
        try:
            img_tags_and_captions = list(MONGO_COLLECTION.find({ "user_id": user_id }).sort("created_at", -1))
            return img_tags_and_captions
        
        except Exception as e:
            error_message = f"Failed to read img tags and captions from MongoDB in read_img_tags_and_captions: {e}"
            app.state.logger.log_error(error_message)
            raise MongoDBError(error_message) from e
        
    @classmethod
    def delete_img_tags_and_captions(cls, s3_key: str) -> None:
        try:
            message = {
                "operation": "delete_img_tags_and_captions",
                "s3_key": s3_key,
            }
            
            kafka_producer.produce(
                topic="mongodb.delete_img_tags_and_captions",
                key=str(s3_key).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )
            
            remaining_messages = kafka_producer.flush(timeout=15)
            
            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("delete_img_tags_and_captions", remaining_messages)
            
            return
        
        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("delete_img_tags_and_captions", e)
    
    @classmethod
    def delete_all_user_img_tags_and_captions(cls, user_id: int) -> None:
        try:
            message = {
                "operation": "delete_all_user_img_tags_and_captions",
                "user_id": user_id,
            }
            
            kafka_producer.produce(
                topic="mongodb.delete_all_user_img_tags_and_captions",
                key=str(user_id).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )
            
            remaining_messages = kafka_producer.flush(timeout=15)
            
            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("delete_all_user_img_tags_and_captions", remaining_messages)
            
            return
        
        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("delete_all_user_img_tags_and_captions", e)
