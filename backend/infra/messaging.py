import os
import json
import time

from confluent_kafka import Producer, Consumer
from dotenv import load_dotenv

from backend.main import app
from backend.config.config import S3_CLIENT, BUCKET_NAME, REDIS_CLIENT, MONGO_COLLECTION

class KafkaConsumeError(Exception):
    "Exception for Kafka consume operations"
    pass
class KafkaMessageError(Exception):
    "Exception for Kafka operations"
    pass

class KafkaMessageProcessError(KafkaMessageError):
    "Exception for Kafka message processing operations"
    pass

class KafkaMessageOperationError(KafkaMessageError):
    "Exception for Kafka message operations"
    pass


def _raise_kafka_consume_error(error: Exception) -> None:
    error_message = f"Failed to consume messages to Kafka: {error}"
    app.state.logger.log_error(error_message)
    raise KafkaConsumeError(error_message) from error

def _raise_kafka_message_error(error: Exception) -> None:
    error_message = f"Error in consumed Kafka message: {error}"
    app.state.logger.log_error(error_message)
    raise KafkaMessageError(error_message) from error

def _raise_kafka_message_process_error(error: Exception) -> None:
    error_message = f"Failed to process Kafka message logic: {error}"
    app.state.logger.log_error(error_message)
    raise KafkaMessageProcessError(error_message) from error

def _raise_kafka_message_operation_error(operation: str) -> None:
    error_message = f"Invalid Kafka message operation: {operation}"
    app.state.logger.log_error(error_message)
    raise KafkaMessageOperationError(error_message)

load_dotenv()
env = os.getenv

kafka_producer = Producer({
    "bootstrap.servers": env("KAFKA_BOOTSTRAP_SERVERS"),
    "queue.buffering.max.messages": 100000,
    "queue.buffering.max.ms": 500,
    "compression.type": "lz4",
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": env("KAFKA_API_KEY"),
    "sasl.password": env("KAFKA_API_SECRET")
})

kafka_consumer = Consumer({
    "bootstrap.servers": env("KAFKA_BOOTSTRAP_SERVERS"),
    "group.id": "msg-queue-for-external-services",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
    "security.protocol": "SASL_SSL",
    "sasl.mechanisms": "PLAIN",
    "sasl.username": env("KAFKA_API_KEY"),
    "sasl.password": env("KAFKA_API_SECRET")
})

kafka_consumer.subscribe([
    "s3.delete_snap",
    "s3.delete_all_snaps",
    "redis.add_new_session",
    "redis.place_thumbnail_img_url",
    "redis.delete_session",
    "redis.add_otp",
    "mongodb.add_img_tags",
    "mongodb.write_img_caption",
    "mongodb.delete_img_tags_and_captions",
    "mongodb.delete_all_user_img_tags_and_captions",
])

BATCH_SIZE = 150
REQ_PER_SECOND = 250
SECONDS_PER_BATCH = BATCH_SIZE / REQ_PER_SECOND

stop_event = None

def process_batch(messages: list):
    success_messages = []
    
    for record in messages:
        if record.error():
            _raise_kafka_message_error(record.error())
        
        try:
            record_msg = json.loads(record.value().decode("utf-8"))
            operation = record_msg.get("operation")
        
            match operation:
                case "delete_snap":
                    s3_key = record_msg["s3_key"]
                    
                    S3_CLIENT.delete_object(
                        Bucket=BUCKET_NAME,
                        Key=s3_key
                    )
                    
                case "delete_all_snaps":
                    user_id = record_msg["user_id"]
                    
                    objects_to_delete = []
                    
                    response = S3_CLIENT.list_objects_v2(Bucket=BUCKET_NAME, Prefix=str(user_id))
                    
                    for object in response["Contents"]:
                        objects_to_delete.append({ "Key": object["Key"] })
                    
                    S3_CLIENT.delete_objects(
                        Bucket=BUCKET_NAME,
                        Delete={ "Objects": objects_to_delete }
                    )
                
                case "add_new_session":
                    session_key = record_msg["session_key"]
                    user_id = record_msg["user_id"]
                    thumbnail_img_url = record_msg["thumbnail_img_url"]
                    created_at = record_msg["created_at"]
                    
                    REDIS_CLIENT.hset(session_key, mapping={
                        "user_id": user_id,
                        "thumbnail_img_url": thumbnail_img_url,
                        "created_at": created_at,
                    })
                    
                    REDIS_CLIENT.expire(session_key, 60 * 60 * 24 * 7 * 4 * 6)
                    
                case "place_thumbnail_img_url":
                    session_key = record_msg["session_key"]
                    thumbnail_img_url = record_msg["thumbnail_img_url"]
                    
                    REDIS_CLIENT.hset(session_key, "thumbnail_img_url", thumbnail_img_url)
                    
                case "delete_session":
                    session_key = record_msg["session_key"]
                    REDIS_CLIENT.delete(session_key)
                    
                case "add_otp":
                    otp = record_msg["otp"]
                    email = record_msg["email"]
                    
                    REDIS_CLIENT.setex(key=email, time=900, value=otp)
                    
                case "add_img_tags":
                    user_id = record_msg["user_id"]
                    s3_key = record_msg["s3_key"]
                    tags = record_msg["tags"]
                    caption = record_msg["caption"]
                    created_at = record_msg["created_at"]
                    
                    MONGO_COLLECTION.insert_one({
                        "user_id": user_id,
                        "s3_key": s3_key,
                        "tags": tags,
                        "caption": caption,
                        "created_at": created_at,
                    })
                    
                case "write_img_caption":
                    s3_key = record_msg["s3_key"]
                    caption = record_msg["caption"]
                    
                    MONGO_COLLECTION.update_one(
                        { "s3_key": s3_key },
                        { "$set": { "caption": caption } },
                    )
                    
                case "delete_img_tags_and_captions":
                    s3_key = record_msg["s3_key"]
                    MONGO_COLLECTION.delete_one({ "s3_key": s3_key })
                    
                case "delete_all_user_img_tags_and_captions":
                    user_id = record_msg["user_id"]
                    MONGO_COLLECTION.delete_many({ "user_id": user_id })
                    
                case _:
                    _raise_kafka_message_operation_error(operation)

            success_messages.append(record)
        
        except KafkaMessageOperationError:
            raise

        except Exception as e:
            _raise_kafka_message_process_error(e)
            
    return True if success_messages else False

def run_consumer(event):
    global stop_event
    stop_event = event
    
    while not stop_event.is_set():
        try:
            start_time = time.time()
            messages_batch = kafka_consumer.consume(BATCH_SIZE, timeout=1.0)
            
            if not messages_batch:
                time.sleep(0.5)
                continue
            
            processed_batch = process_batch(messages_batch)
            
            if processed_batch:
                kafka_consumer.commit(asynchronous=False)
            
            elapsed_time = time.time() - start_time
            time.sleep(max(0.0, SECONDS_PER_BATCH - elapsed_time))
            
        except KafkaMessageError:
            raise
        
        except Exception as e:
            _raise_kafka_consume_error(e)

