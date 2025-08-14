import os
import uuid
from datetime import datetime

import redis
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

class RedisSession:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=env("REDIS_HOST"),
            port=int(env("REDIS_PORT")),
            decode_responses=True,
            username="default",
            password=env("REDIS_USER_PASS"),
        )

    def add_new_session(self, user_id: int) -> str:
        session_id = str(uuid.uuid4())
        session_key = f"session:{session_id}"
        
        self.redis_client.hset(session_key, mapping={
            "user_id": user_id,
            "created_at": datetime.now(),
        })

        return session_key

    def get_session(self, session_key: str) -> dict:
        return self.redis_client.hgetall(session_key)

    def delete_session(self, session_key: str) -> None:
        self.redis_client.delete(session_key)
