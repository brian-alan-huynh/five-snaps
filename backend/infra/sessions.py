import os
import json
import uuid
from datetime import datetime

from dotenv import load_dotenv

from .messaging import kafka_producer
from ..config import REDIS_CLIENT

load_dotenv()
env = os.getenv

class Redis:
    @staticmethod
    def add_new_session(user_id: int, oauth_access_token: str) -> str | bool:
        try: 
            session_id = str(uuid.uuid4())
            session_key = f"session:{session_id}"
            
            message = {
                "operation": "add_new_session",
                "session_key": session_key,
                "user_id": user_id,
                "oauth_access_token": oauth_access_token,
                "created_at": datetime.now(),
            }

            kafka_producer.produce(
                topic="redis.add_new_session",
                value=json.dumps(message).encode("utf-8"),
            )

            kafka_producer.flush()

            return session_key

        except Exception:
            return False

    @staticmethod
    def get_session(session_key: str) -> dict | bool:
        try:
            return REDIS_CLIENT.hgetall(session_key)
        
        except Exception:
            return False

    @staticmethod
    def delete_session(session_key: str) -> bool:
        try:
            message = {
                "operation": "delete_session",
                "session_key": session_key,
            }

            kafka_producer.produce(
                topic="redis.delete_session",
                value=json.dumps(message).encode("utf-8"),
            )

            kafka_producer.flush()

            return True

        except Exception:
            return False
