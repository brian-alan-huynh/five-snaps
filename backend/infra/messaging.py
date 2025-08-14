import os
import json
import time

from confluent_kafka import Producer, Consumer
from dotenv import load_dotenv

from ..config import S3_CLIENT, BUCKET_NAME

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
    "s3.upload_pfp",
    "s3.delete_pfp",
])

BATCH_SIZE = 100
REQ_PER_SECOND = 200
SECONDS_PER_BATCH = BATCH_SIZE / REQ_PER_SECOND

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
                case "upload_pfp":
                    s3_key = record_msg["s3_key"]
                    file_content = bytes.fromhex(record_msg["file_content"])
                    content_type = record_msg["content_type"]
                
                    S3_CLIENT.put_object(
                        Bucket=BUCKET_NAME,
                        Key=s3_key,
                        Body=file_content,
                        ContentType=content_type,
                        ACL='public-read'
                    )

                case "delete_pfp":
                    s3_key = record_msg["s3_key"]
                    
                    S3_CLIENT.delete_object(
                        Bucket=BUCKET_NAME,
                        Key=s3_key
                    )
                    
                case _:
                    # Once backend is completed, add log here
                    continue
            
            success_messages.append(record)
        
        except Exception as e:
            # Once backend is completed, add log here
            continue
        
    return True if success_messages else False

def run_consumer():
    while True:
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
