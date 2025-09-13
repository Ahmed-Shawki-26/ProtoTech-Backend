#!/usr/bin/env python3
"""
A utility script to read and display all records from the 'users' table.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

# --- Configuration ---
# Add the 'src' directory to the Python path to allow imports of your modules
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), 'src')))

# Load environment variables from .env file
load_dotenv()

# Import your database URL AFTER setting the path and loading dotenv
DATABASE_URL=os.getenv("DATABASE_URL")

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

def show_all_users():
    """
    Connects to the database and prints all rows from the 'users' table.
    """
    print(f"--- Querying Users from Database ---")
    print(f"Target Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print("-" * 35)

    try:
        with get_db_session() as db:
            if not db:
                return

            # Check if the 'users' table exists
            inspector = inspect(db.get_bind())
            if not inspector.has_table('employee'):
                print("Table 'users' does not exist in the database.")
                return

            # Execute the SELECT statement
            select_statement = text('SELECT * FROM users ORDER BY created_at;')
            result = db.execute(select_statement).fetchall()

            if not result:
                print("No users found in the 'users' table.")
                return

            print(f"Found {len(result)} user(s):\n")
            
            # Get column names from the first row's keys
            columns = result[0]._fields
            
            # Pretty-print the header
            header = " | ".join(f"{col:<20}" for col in columns)
            print(header)
            print("-" * len(header))

            # Pretty-print each row
            for row in result:
                row_data = []
                for item in row:
                    # Truncate long strings for better display
                    display_item = str(item)
                    if len(display_item) > 18:
                        display_item = display_item[:15] + "..."
                    row_data.append(f"{display_item:<20}")
                print(" | ".join(row_data))

    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    show_all_users()