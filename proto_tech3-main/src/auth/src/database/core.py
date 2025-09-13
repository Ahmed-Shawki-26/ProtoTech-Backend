from typing import Annotated
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os
from dotenv import load_dotenv
from src.auth.src.logging import logger
load_dotenv()

""" Get DATABASE_URL from environment variables """
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.warning("DATABASE_URL not found in environment variables, falling back to SQLite")
    DATABASE_URL = "sqlite:///./proto.db"

logger.info(f"Using database: Postgresql " if "postgresql" in DATABASE_URL else "Using database: SQLite")

# Create engine with appropriate settings for PostgreSQL vs SQLite
if DATABASE_URL.startswith("postgresql://"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False  # Set to True for SQL debugging
    )
else:
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False  # Set to True for SQL debugging
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
