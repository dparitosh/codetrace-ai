"""
Test PostgreSQL Connection
Quick script to verify database connection parameters
"""

import asyncio
import asyncpg
import sys
import os

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.config import settings

async def test_connection():
    """Test PostgreSQL connection with current settings"""
    print("Testing PostgreSQL connection...")
    print(f"Host: {settings.POSTGRES_HOST}")
    print(f"Port: {settings.POSTGRES_PORT}")
    print(f"User: {settings.POSTGRES_USER}")
    print(f"Database: {settings.POSTGRES_DB}")
    
    # Try to connect to PostgreSQL server
    server_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"
    
    try:
        print("\n1. Testing connection to PostgreSQL server...")
        conn = await asyncpg.connect(server_url)
        print("✅ Successfully connected to PostgreSQL server")
        
        # Test basic query
        result = await conn.fetchval("SELECT version();")
        print(f"📊 PostgreSQL version: {result}")
        
        # List databases
        databases = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false;")
        print(f"📋 Available databases: {[db['datname'] for db in databases]}")
        
        await conn.close()
        
        # Try to connect to specific database
        print(f"\n2. Testing connection to specific database '{settings.POSTGRES_DB}'...")
        db_url = settings.postgres_url
        
        try:
            db_conn = await asyncpg.connect(db_url)
            print(f"✅ Successfully connected to database '{settings.POSTGRES_DB}'")
            await db_conn.close()
        except asyncpg.InvalidCatalogNameError:
            print(f"⚠️ Database '{settings.POSTGRES_DB}' does not exist - will be created during initialization")
        
        print("\n✅ PostgreSQL connection test completed successfully!")
        
    except asyncpg.InvalidPasswordError:
        print("❌ Authentication failed!")
        print(f"The password for user '{settings.POSTGRES_USER}' is incorrect.")
        print("Please update the DB_PASSWORD in your .env file")
        
    except asyncpg.CannotConnectNowError:
        print("❌ Cannot connect to PostgreSQL server!")
        print(f"PostgreSQL might not be running on {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        print("Please check if PostgreSQL service is running")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
