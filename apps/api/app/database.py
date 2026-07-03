import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://iporadar:iporadar_dev@postgres:5432/iporadar"
)

# We use sync driver psycopg2 for Phase 1 simplicity, since inference and 
# feature extraction will be blocking operations anyway (or handled via threadpool).
engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
