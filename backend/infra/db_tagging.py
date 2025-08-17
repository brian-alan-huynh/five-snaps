import json
from datetime import datetime

from .messaging import kafka_producer
from ..config import MONGO_COLLECTION

class MongoDB:
    @staticmethod
    def add_img_tags(user_id: int, s3_key: str, tags: list[str]) -> bool:
        try:
            message = {
                "operation": "add_img_tags",
                "user_id": user_id,
                "s3_key": s3_key,
                "tags": tags,
                "caption": "",
                "created_at": datetime.now(),
            }
            
            kafka_producer.produce(
                topic="mongodb.add_img_tags",
                value=json.dumps(message).encode("utf-8"),
            )
            
            kafka_producer.flush()
            
            return True
        
        except Exception:
            return False

    @staticmethod
    def write_img_caption(s3_key: str, caption: str) -> bool:
        try:
            message = {
                "operation": "write_img_caption",
                "s3_key": s3_key,
                "caption": caption,
            }
            
            kafka_producer.produce(
                topic="mongodb.write_img_caption",
                value=json.dumps(message).encode("utf-8"),
            )
            
            kafka_producer.flush()
            
            return True
        
        except Exception:
            return False

    @staticmethod
    def read_img_tags_and_captions(user_id: int) -> list[dict[str, str | datetime]] | bool:
        try:
            img_tags = list(MONGO_COLLECTION.find({ "user_id": user_id }).sort("created_at", -1))
            return img_tags
        
        except Exception:
            return False
