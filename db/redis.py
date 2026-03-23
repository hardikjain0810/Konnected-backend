import redis
from core.config import settings
import time

class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )

    def set_auth_session(self, email: str, otp: str, country: str, birth_year: int):
        key = f"otp:{email}"
        data = f"{otp}:{country}:{birth_year}"
        self.client.setex(key, settings.OTP_TTL, data)

    def get_auth_session(self, email: str) -> tuple:
        key = f"otp:{email}"
        data = self.client.get(key)
        if not data:
            return None, None, None
        parts = data.split(':')
        if len(parts) == 3:
            return parts[0], parts[1], int(parts[2])
        return None, None, None

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

redis_client = RedisClient()
