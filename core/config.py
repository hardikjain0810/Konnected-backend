from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # New Static OTP settings
    APP_ENV: str = os.getenv("APP_ENV", "development") # Default to dev
    STATIC_OTP: str = os.getenv("STATIC_OTP", "123456")

    # App Config
    SECRET_KEY: str = "Konnected"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:12345678@localhost:5432/Konnected"

    # Railway will provide this automatically if you linked the service
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # Fallbacks for local dev
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = 0
    
    # OTP Config
    OTP_TTL: int = 600  # 10 minutes

    # Email Config
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "your_email@gmail.com"
    SMTP_PASS: str = "your_app_password"
    OTP_SEND_LIMIT: int = 5
    OTP_VERIFY_LIMIT: int = 10

    # Live session / ZEGO config
    ZEGO_APP_ID: int = int(os.getenv("ZEGO_APP_ID", 339934320))
    ZEGO_SERVER_SECRET: str = os.getenv("ZEGO_SERVER_SECRET", "d6521464dc21868c4263c6fc08c31abe")
    ZEGO_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("ZEGO_TOKEN_EXPIRE_SECONDS", 1800))
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
