#!/usr/bin/env python3
"""
Migration script to add new tables from proto_tech3-main
This script will:
1. Add the new pcb_orders table
2. Improve existing tables with better field types and constraints
3. Add missing indexes
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def run_migration():
    """Run the database migration"""
    
    # Get database URL from environment or use default
    database_url = os.getenv('DATABASE_URL', 'sqlite:///proto.db')
    
    print(f"🔧 Connecting to database: {database_url}")
    
    # Create engine
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            print("📋 Starting database migration...")
            
            # Check if we're using PostgreSQL
            if 'postgresql' in database_url:
                print("🐘 Detected PostgreSQL database")
                migrate_postgresql(conn)
            else:
                print("🗃️ Detected SQLite database")
                migrate_sqlite(conn)
            
            # Commit transaction
            trans.commit()
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"❌ Migration failed: {e}")
            raise

def migrate_postgresql(conn):
    """Migrate PostgreSQL database"""
    
    # Create enums if they don't exist
    print("📝 Creating enums...")
    
    # Check if enums exist
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'pcb_orderstatus'
        );
    """))
    
    if not result.scalar():
        conn.execute(text("""
            CREATE TYPE pcb_orderstatus AS ENUM (
                'PENDING', 'PROCESSING', 'COMPLETED', 'SHIPPED', 'CANCELLED', 'FAILED'
            );
        """))
        print("✅ Created pcb_orderstatus enum")
    
    # Create pcb_orders table if it doesn't exist
    print("📋 Creating pcb_orders table...")
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pcb_orders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            order_number VARCHAR UNIQUE NOT NULL,
            status pcb_orderstatus NOT NULL DEFAULT 'PENDING',
            width_mm FLOAT NOT NULL,
            height_mm FLOAT NOT NULL,
            final_price_egp FLOAT NOT NULL,
            stripe_payment_intent_id VARCHAR,
            base_material VARCHAR NOT NULL,
            manufacturing_parameters JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );
    """))
    
    # Create indexes for pcb_orders
    print("🔍 Creating indexes for pcb_orders...")
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_pcb_orders_user_id ON pcb_orders(user_id);
    """))
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_pcb_orders_order_number ON pcb_orders(order_number);
    """))
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_pcb_orders_stripe_payment_intent_id ON pcb_orders(stripe_payment_intent_id);
    """))
    
    # Add updated_at trigger for pcb_orders
    print("⏰ Creating updated_at trigger for pcb_orders...")
    
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """))
    
    conn.execute(text("""
        DROP TRIGGER IF EXISTS update_pcb_orders_updated_at ON pcb_orders;
        CREATE TRIGGER update_pcb_orders_updated_at
            BEFORE UPDATE ON pcb_orders
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """))
    
    print("✅ PostgreSQL migration completed!")

def migrate_sqlite(conn):
    """Migrate SQLite database"""
    
    # Create pcb_orders table if it doesn't exist
    print("📋 Creating pcb_orders table...")
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS pcb_orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            order_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            width_mm REAL NOT NULL,
            height_mm REAL NOT NULL,
            final_price_egp REAL NOT NULL,
            stripe_payment_intent_id TEXT,
            base_material TEXT NOT NULL,
            manufacturing_parameters TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """))
    
    # Create indexes for pcb_orders
    print("🔍 Creating indexes for pcb_orders...")
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_pcb_orders_user_id ON pcb_orders(user_id);
    """))
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_pcb_orders_order_number ON pcb_orders(order_number);
    """))
    
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_pcb_orders_stripe_payment_intent_id ON pcb_orders(stripe_payment_intent_id);
    """))
    
    print("✅ SQLite migration completed!")

def check_migration_status():
    """Check the current migration status"""
    
    database_url = os.getenv('DATABASE_URL', 'sqlite:///proto.db')
    engine = create_engine(database_url)
    
    with engine.connect() as conn:
        try:
            # Check if pcb_orders table exists
            if 'postgresql' in database_url:
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'pcb_orders'
                    );
                """))
            else:
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name='pcb_orders';
                """))
            
            table_exists = result.scalar()
            
            if table_exists:
                print("✅ pcb_orders table already exists")
                
                # Count records
                if 'postgresql' in database_url:
                    count_result = conn.execute(text("SELECT COUNT(*) FROM pcb_orders"))
                else:
                    count_result = conn.execute(text("SELECT COUNT(*) FROM pcb_orders"))
                
                count = count_result.scalar()
                print(f"📊 pcb_orders table has {count} records")
            else:
                print("❌ pcb_orders table does not exist")
                
        except Exception as e:
            print(f"⚠️ Error checking migration status: {e}")

if __name__ == "__main__":
    print("🚀 ProtoTech Database Migration Tool")
    print("=" * 50)
    
    # Check current status
    print("📊 Checking current migration status...")
    check_migration_status()
    
    print("\n🔄 Running migration...")
    run_migration()
    
    print("\n📊 Final status check...")
    check_migration_status()
    
    print("\n🎉 Migration process completed!")
