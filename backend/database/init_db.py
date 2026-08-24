"""
Database setup and initialization script
"""

import asyncio
import asyncpg
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.config import settings
from database.connection import engine, Base

async def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    # Connect to PostgreSQL server (not the specific database)
    server_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"
    
    try:
        conn = await asyncpg.connect(server_url)
        
        # Check if database exists
        db_exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            settings.POSTGRES_DB
        )
        
        if not db_exists:
            # Create database using parameterized query for safety
            # Note: Database names cannot be parameterized, but we validate the name
            db_name = settings.POSTGRES_DB
            # Validate database name to prevent injection
            if not db_name.replace('_', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid database name: {db_name}")
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Created database: {db_name}")
        else:
            print(f"Database {settings.POSTGRES_DB} already exists")
        
        await conn.close()
        
    except asyncpg.InvalidPasswordError:
        print(f"Authentication failed for user '{settings.POSTGRES_USER}'")
        print("Please check your PostgreSQL credentials in .env file")
        raise
    except asyncpg.CannotConnectNowError:
        print(f"Cannot connect to PostgreSQL server at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        print("Please make sure PostgreSQL is running")
        raise
    except Exception as e:
        print(f"Error creating database: {e}")
        print("Make sure PostgreSQL is running and credentials are correct")
        raise

def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        print("All database tables created successfully")
    except Exception as e:
        print(f"Error creating tables: {e}")
        raise

async def init_database():
    """Initialize the complete database setup"""
    print("Initializing database setup...")
    
    # Create database if not exists
    await create_database_if_not_exists()
    
    # Create tables
    create_tables()
    
    print("Database initialization completed!")

if __name__ == "__main__":
    asyncio.run(init_database())
