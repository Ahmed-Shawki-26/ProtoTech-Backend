#!/usr/bin/env python3
"""
Utility script to drop the 'alembic_version' table (reset Alembic history).
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# Add the 'src' directory to the Python path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), 'src')))

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_db_session():
    """Context manager for a database session."""
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set in your .env file. Aborting.")
        return
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def drop_alembic_version():
    """Drops the Alembic version table."""
    print(f"--- Dropping alembic_version table ---")
    print(f"Target Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("-" * 40)

    try:
        with get_db_session() as db:
            if not db:
                return

            db.execute(text("DROP TABLE IF EXISTS alembic_version;"))
            db.execute(text("DROP TABLE IF EXISTS todos;"))
            db.execute(text("DROP TABLE IF EXISTS users;"))
            db.execute(text("DROP TABLE IF EXISTS user_carts;"))
            db.execute(text("DROP TABLE IF EXISTS order_items;"))
            db.execute(text("DROP TABLE IF EXISTS orders;"))
            db.commit()
            print("✅  table deleted successfully.")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    drop_alembic_version()
