#!/usr/bin/env python3
"""Check indexes and constraints on phoneNumber"""

from app import create_app
from models import db

app = create_app('development')

with app.app_context():
    with db.engine.connect() as conn:
        # Check table schema
        result = conn.execute(db.text("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='users'
        """))
        table_sql = result.fetchone()
        
        if table_sql:
            schema = table_sql[0]
            print("Users table schema:")
            print("=" * 80)
            print(schema)
            print("=" * 80)
            print()
            
        # Check for indexes on phoneNumber
        result = conn.execute(db.text("""
            SELECT name, sql FROM sqlite_master 
            WHERE type='index' AND tbl_name='users' AND sql IS NOT NULL
        """))
        
        indexes = result.fetchall()
        print("Indexes on users table:")
        print("=" * 80)
        for idx_name, idx_sql in indexes:
            print(f"{idx_name}:")
            print(f"  {idx_sql}")
            print()
        print("=" * 80)
        print()
        
        # Try to insert duplicate phone number
        print("Testing duplicate phone number...")
        try:
            # Check if phone exists
            result = conn.execute(db.text("""
                SELECT phoneNumber, first_name, last_name 
                FROM users 
                WHERE phoneNumber = '01700000000'
                LIMIT 1
            """))
            existing = result.fetchone()
            
            if existing:
                print(f"✅ Found existing user with 01700000000: {existing[1]} {existing[2]}")
                print("   This means the phone number is already in use")
            else:
                print("   No existing user with 01700000000")
                
        except Exception as e:
            print(f"❌ Error: {e}")
