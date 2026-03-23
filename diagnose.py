import redis
import psycopg2
from core.config import settings
from sqlalchemy import create_engine
from models.database_models import Base

def check_connections():
    print("Checking Redis connection...")
    try:
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB)
        r.ping()
        print("Redis is UP")
    except Exception as e:
        print(f"Redis is DOWN: {e}")

    print("\nChecking PostgreSQL connection...")
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        conn.close()
        print("PostgreSQL is UP")
    except Exception as e:
        print(f"PostgreSQL is DOWN: {e}")

    print("\nChecking Database Tables...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(bind=engine)
        print("Database tables verified/created")
    except Exception as e:
        print(f"Error creating/verifying tables: {e}")

if __name__ == "__main__":
    check_connections()
