from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

db_url = "postgresql://postgres:12345678@localhost:5432/Konnected"

engine = create_engine(db_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()