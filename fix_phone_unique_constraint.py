#!/usr/bin/env python3
"""
Fix UNIQUE constraint on phoneNumber to allow siblings with same phone
This script removes the UNIQUE constraint from the phoneNumber column
"""

from app import create_app
from models import db
import sys

def fix_phone_constraint():
    """Remove UNIQUE constraint from phoneNumber column"""
    app = create_app('production')
    
    with app.app_context():
        print("🔧 Fixing phoneNumber UNIQUE constraint...")
        print("=" * 60)
        
        try:
            # For SQLite, we need to recreate the table without the constraint
            # Check if we're using SQLite
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            
            if 'sqlite' in db_uri:
                print("📊 Detected SQLite database")
                print("⚠️  SQLite requires table recreation to modify constraints")
                print()
                
                # SQLite approach: Create new table without constraint, copy data, swap tables
                with db.engine.connect() as conn:
                    # Start transaction
                    trans = conn.begin()
                    
                    try:
                        # 1. Check if constraint exists
                        result = conn.execute(db.text("""
                            SELECT sql FROM sqlite_master 
                            WHERE type='table' AND name='users'
                        """))
                        table_sql = result.fetchone()[0]
                        
                        print("📋 Current table schema:")
                        print(table_sql)
                        print()
                        
                        if 'UNIQUE' in table_sql and 'phoneNumber' in table_sql:
                            print("⚠️  Found UNIQUE constraint on phoneNumber")
                            print("🔄 Recreating table without UNIQUE constraint...")
                            
                            # 2. Create temporary table
                            conn.execute(db.text("""
                                CREATE TABLE users_new (
                                    id INTEGER PRIMARY KEY,
                                    phoneNumber VARCHAR(20) NOT NULL,
                                    first_name VARCHAR(100) NOT NULL,
                                    last_name VARCHAR(100) NOT NULL,
                                    email VARCHAR(255) UNIQUE,
                                    password_hash VARCHAR(255),
                                    role TEXT NOT NULL,
                                    profile_image TEXT,
                                    date_of_birth DATE,
                                    address TEXT,
                                    guardian_name VARCHAR(200),
                                    guardian_phone VARCHAR(20),
                                    mother_name VARCHAR(200),
                                    emergency_contact VARCHAR(20),
                                    admission_date DATE,
                                    exam_fee NUMERIC(10, 2) DEFAULT 0.00,
                                    others_fee NUMERIC(10, 2) DEFAULT 0.00,
                                    sms_count INTEGER DEFAULT 0,
                                    is_active BOOLEAN DEFAULT 1,
                                    last_login TIMESTAMP,
                                    is_archived BOOLEAN DEFAULT 0,
                                    archived_at TIMESTAMP,
                                    archived_by INTEGER,
                                    archive_reason TEXT,
                                    created_at TIMESTAMP NOT NULL,
                                    updated_at TIMESTAMP,
                                    FOREIGN KEY(archived_by) REFERENCES users(id)
                                )
                            """))
                            
                            # 3. Copy data
                            print("📦 Copying existing data...")
                            conn.execute(db.text("""
                                INSERT INTO users_new 
                                SELECT * FROM users
                            """))
                            
                            # 4. Drop old table
                            print("🗑️  Dropping old table...")
                            conn.execute(db.text("DROP TABLE users"))
                            
                            # 5. Rename new table
                            print("📝 Renaming new table...")
                            conn.execute(db.text("ALTER TABLE users_new RENAME TO users"))
                            
                            # 6. Create index on phoneNumber for performance
                            print("🔍 Creating index on phoneNumber...")
                            conn.execute(db.text("""
                                CREATE INDEX IF NOT EXISTS idx_users_phoneNumber 
                                ON users(phoneNumber)
                            """))
                            
                            trans.commit()
                            print()
                            print("✅ SUCCESS! phoneNumber can now be shared by multiple students (siblings)")
                            print("👨‍👩‍👧‍👦 You can now add siblings with the same phone number")
                            
                        else:
                            print("✅ No UNIQUE constraint found on phoneNumber - already fixed!")
                            trans.rollback()
                            
                    except Exception as e:
                        trans.rollback()
                        print(f"❌ Error during migration: {e}")
                        raise
                        
            else:
                # MySQL/PostgreSQL approach
                print("📊 Detected MySQL/PostgreSQL database")
                print("🔧 Dropping UNIQUE constraint...")
                
                try:
                    # Try to drop the constraint
                    with db.engine.connect() as conn:
                        # This syntax works for MySQL
                        conn.execute(db.text("""
                            ALTER TABLE users 
                            DROP INDEX phoneNumber
                        """))
                        conn.commit()
                    
                    print("✅ SUCCESS! Unique constraint removed")
                    
                except Exception as e:
                    if 'exist' in str(e).lower():
                        print("✅ No UNIQUE constraint found - already fixed!")
                    else:
                        print(f"⚠️  Warning: {e}")
                        
            print()
            print("=" * 60)
            print("🎉 Migration completed!")
            print()
            print("Next steps:")
            print("  1. Restart your application")
            print("  2. Try adding students with the same phone number")
            print()
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    fix_phone_constraint()
