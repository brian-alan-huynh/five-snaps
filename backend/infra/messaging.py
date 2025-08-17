import os
import json
import time

from confluent_kafka import Producer, Consumer
from dotenv import load_dotenv

from ..config import S3_CLIENT, BUCKET_NAME, REDIS_CLIENT, MONGO_COLLECTION

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
    "redis.add_new_session",
    "redis.place_thumbnail_img_url",
    "redis.delete_session",
    "mongodb.add_img_tags",
    "mongodb.write_img_caption",
])

BATCH_SIZE = 100
REQ_PER_SECOND = 200
SECONDS_PER_BATCH = BATCH_SIZE / REQ_PER_SECOND

stop_event = None

def process_batch(messages: list):
    success_messages = []
    
    for record in messages:
        if record.error():
            # Once backend is completed, add log here
            continue
        
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
                    
                case "place_thumbnail_img_url":
                    session_key = record_msg["session_key"]
                    thumbnail_img_url = record_msg["thumbnail_img_url"]
                    
                    REDIS_CLIENT.hset(session_key, "thumbnail_img_url", thumbnail_img_url)
                    
                case "delete_session":
                    session_key = record_msg["session_key"]
                    REDIS_CLIENT.delete(session_key)
                    
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
                    
                case _:
                    # Once backend is completed, add log here
                    continue
            
            success_messages.append(record)
        
        except Exception as e:
            # Once backend is completed, add log here
            continue
        
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

        except Exception as e:
            # Once backend is completed, add log here
            time.sleep(1.0)
            continue
