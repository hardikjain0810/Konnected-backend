import redis
from core.config import settings
import time
import json

class RedisClient:
    def __init__(self):
        # Use the full URL if it exists, otherwise fallback to individual settings
        if settings.REDIS_URL:
            self.client = redis.from_url(
                settings.REDIS_URL, 
                decode_responses=True
            )
        else:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )

    def set_auth_session(self, email: str, otp: str, country: str, birth_year: int, user_role: str = None):
        key = f"otp:{email}"
        # Store role if provided (for signup), otherwise use empty string (for login)
        role_str = user_role if user_role else ""
        data = f"{otp}:{country}:{birth_year}:{role_str}"
        self.client.setex(key, settings.OTP_TTL, data)

    def get_auth_session(self, email: str) -> tuple:
        key = f"otp:{email}"
        data = self.client.get(key)
        if not data:
            return None, None, None, None
        parts = data.split(':')
        if len(parts) >= 3:
            otp = parts[0]
            country = parts[1]
            birth_year = int(parts[2])
            role = parts[3] if len(parts) > 3 and parts[3] else None
            return otp, country, birth_year, role
        return None, None, None, None

    def delete_otp(self, email: str):
        key = f"otp:{email}"
        self.client.delete(key)

    def increment_send_count(self, email: str) -> int:
        key = f"rate_limit:send:{email}:{time.strftime('%Y-%m-%d-%H')}"
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, 3600)  # 1 hour
        return count

    def increment_verify_count(self, email: str) -> int:
        key = f"rate_limit:verify:{email}:{time.strftime('%Y-%m-%d-%H')}"
        count = self.client.incr(key)
        if count == 1:
            self.client.expire(key, 3600)  # 1 hour
        return count

    def check_send_limit(self, email: str) -> bool:
        key = f"rate_limit:send:{email}:{time.strftime('%Y-%m-%d-%H')}"
        count = self.client.get(key)
        if count and int(count) >= settings.OTP_SEND_LIMIT:
            return False
        return True

    def check_verify_limit(self, email: str) -> bool:
        key = f"rate_limit:verify:{email}:{time.strftime('%Y-%m-%d-%H')}"
        count = self.client.get(key)
        if count and int(count) >= settings.OTP_VERIFY_LIMIT:
            return False
        return True

    # -------------------------------
    # Live session helper methods
    # -------------------------------
    def set_live_session_meta(self, room_id: str, payload: dict, ttl_seconds: int = 7200):
        key = f"live:room:meta:{room_id}"
        self.client.setex(key, ttl_seconds, json.dumps(payload))

    def get_live_session_meta(self, room_id: str) -> dict:
        key = f"live:room:meta:{room_id}"
        val = self.client.get(key)
        return json.loads(val) if val else {}

    def set_user_active_room(self, actor_id: str, room_id: str, ttl_seconds: int = 7200):
        key = f"live:user:active:{actor_id}"
        self.client.setex(key, ttl_seconds, room_id)

    def get_user_active_room(self, actor_id: str) -> str:
        key = f"live:user:active:{actor_id}"
        return self.client.get(key)

    def clear_user_active_room(self, actor_id: str):
        key = f"live:user:active:{actor_id}"
        self.client.delete(key)

    def add_room_participant(self, room_id: str, actor_id: str, ttl_seconds: int = 7200):
        key = f"live:room:participants:{room_id}"
        self.client.sadd(key, actor_id)
        self.client.expire(key, ttl_seconds)

    def get_room_participants(self, room_id: str) -> list:
        key = f"live:room:participants:{room_id}"
        return list(self.client.smembers(key))

    def clear_room_participants(self, room_id: str):
        key = f"live:room:participants:{room_id}"
        self.client.delete(key)

redis_client = RedisClient()
