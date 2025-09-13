#!/usr/bin/env python3
"""
A utility script to delete all records from the 'users' table.

DANGER: This script will permanently delete all user data.
It should be used with extreme caution, primarily in development environments.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# --- Configuration ---
# Add the 'src' directory to the Python path to allow imports of your modules
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), 'src')))

# Load environment variables from .env file
load_dotenv()

# Import your database core components AFTER setting the path
from src.database.core import DATABASE_URL, engine

def clear_users_table():
    """
    Connects to the database and deletes all rows from the 'users' table.
    """
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set in your .env file. Aborting.")
        return

    print("--- DANGER ---")
    print("This script will permanently delete all records from the 'users' table.")
    print(f"Target Database: {DATABASE_URL.split('@')[-1]}") # Obfuscate user/pass
    
    # Final confirmation prompt
    confirm = input("Are you sure you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation cancelled by user.")
        return

    try:
        # Create a new session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Check if the 'users' table exists before trying to delete from it
        inspector = inspect(engine)
        if not inspector.has_table('users'):
            print("Table 'users' does not exist in the database. Nothing to delete.")
            db.close()
            return

        print("\nDeleting all records from the 'users' table...")
        
        # Execute the DELETE statement
        # Using text() is recommended for raw SQL statements with SQLAlchemy
        delete_statement = text('DELETE FROM users;')
        result = db.execute(delete_statement)
        db.commit()

        print(f"Successfully deleted {result.rowcount} user records.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if 'db' in locals() and db.is_active:
            db.rollback()
            print("Transaction has been rolled back.")
    finally:
        if 'db' in locals() and db.is_active:
            db.close()
            print("Database connection closed.")


if __name__ == "__main__":
    clear_users_table()