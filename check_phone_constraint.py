#!/usr/bin/env python3
"""Check if phoneNumber has UNIQUE constraint"""

from app import create_app
from models import db

app = create_app('development')

with app.app_context():
    with db.engine.connect() as conn:
        result = conn.execute(db.text("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='users'
        """))
        table_sql = result.fetchone()
        
        if table_sql:
            schema = table_sql[0]
            print("Current users table schema:")
            print("=" * 80)
            print(schema)
            print("=" * 80)
            print()
            
            if 'UNIQUE' in schema and 'phoneNumber' in schema:
                print("❌ FOUND: phoneNumber has UNIQUE constraint")
                print("   This prevents multiple students from sharing a phone number")
                print()
                print("💡 Run: python3 fix_phone_unique_constraint.py")
            else:
                print("✅ phoneNumber does NOT have UNIQUE constraint")
                print("   Multiple students can share the same phone number")
        else:
            print("⚠️  users table not found")
