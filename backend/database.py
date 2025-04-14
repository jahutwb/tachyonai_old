from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

from .config import Config, ConfigSettingEnum

load_dotenv()

DATABASE_URL = Config.get_database_url()

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Funkcja pomocnicza do uzyskania sesji bazy danych."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()