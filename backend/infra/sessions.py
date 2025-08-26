import os
import json
import uuid
from datetime import datetime

from dotenv import load_dotenv

from messaging import kafka_producer
from backend.main import app
from backend.config.config import REDIS_CLIENT

class RedisError(Exception):
    "Exception for Redis operations"
    pass

class KafkaProduceDeliveryError(RedisError):
    "Exception for Kafka producer message delivery"
    pass

class KafkaProduceOperationError(RedisError):
    "Exception for Kafka producer operations"
    pass

load_dotenv()
env = os.getenv

class Redis:
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
    def add_new_session(cls, user_id: int) -> str:
        try: 
            session_id = str(uuid.uuid4())
            session_key = f"session:{session_id}"
            
            message = {
                "operation": "add_new_session",
                "session_key": session_key,
                "user_id": user_id,
                "thumbnail_img_url": "",
                "created_at": datetime.now(),
            }

            kafka_producer.produce(
                topic="redis.add_new_session",
                key=str(session_key).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )

            remaining_messages = kafka_producer.flush(timeout=15)

            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("add_new_session", remaining_messages)

            return session_key

        except KafkaProduceDeliveryError:
            raise

        except Exception as e:
            cls._raise_kafka_message_produce_failure("add_new_session", e)

    @staticmethod
    def get_session(session_key: str) -> dict | list:
        try:
            return REDIS_CLIENT.hgetall(session_key)
        
        except Exception as e:
            error_message = f"Failed to get session from Redis in get_session: {e}"
            
            app.state.logger.log_error(error_message)
            raise RedisError(error_message) from e
        
    @classmethod
    def place_thumbnail_img_url(cls, session_key: str, thumbnail_img_url: str) -> None:
        try:
            message = {
                "operation": "place_thumbnail_img_url",
                "session_key": session_key,
                "thumbnail_img_url": thumbnail_img_url,
            }

            kafka_producer.produce(
                topic="redis.place_thumbnail_img_url",
                key=str(session_key).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )

            remaining_messages = kafka_producer.flush(timeout=15)

            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("place_thumbnail_img_url", remaining_messages)

            return
        
        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("place_thumbnail_img_url", e)

    @classmethod
    def delete_session(cls, session_key: str) -> None:
        try:
            message = {
                "operation": "delete_session",
                "session_key": session_key,
            }

            kafka_producer.produce(
                topic="redis.delete_session",
                key=str(session_key).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )

            remaining_messages = kafka_producer.flush(timeout=15)

            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("delete_session", remaining_messages)

            return

        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("delete_session", e)
        
    @classmethod
    def add_otp(cls, otp: int, email: str) -> None:
        try:
            message = {
                "operation": "add_otp",
                "otp": otp,
                "email": email,
            }

            kafka_producer.produce(
                topic="redis.add_otp",
                key=str(email).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
            )

            remaining_messages = kafka_producer.flush(timeout=15)

            if remaining_messages > 0:
                cls._raise_kafka_message_delivery_failure("add_otp", remaining_messages)

            return
        
        except KafkaProduceDeliveryError:
            raise
        
        except Exception as e:
            cls._raise_kafka_message_produce_failure("add_otp", e)
        
    @staticmethod
    def verify_otp(user_otp: int, email: str) -> bool:
        try:
            otp = REDIS_CLIENT.get(email)
            
            if not otp or int(otp) != user_otp:
                return False
            
            return True
            
        except Exception as e:
            error_message = f"Failed to verify OTP in verify_otp: {e}"
            
            app.state.logger.log_error(error_message)
            raise RedisError(error_message) from e
