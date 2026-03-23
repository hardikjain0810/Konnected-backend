from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App Config
    SECRET_KEY: str = "Konnected"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:12345678@localhost:5432/Konnected"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
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
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
