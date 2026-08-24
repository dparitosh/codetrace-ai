"""
Create PostgreSQL database and schema for CodeAce AI
Uses default PostgreSQL credentials and creates the database on port 5433
"""

import asyncio
import asyncpg
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import os

# Database configuration
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "codeace_ai"
DB_USER = "postgres"
DB_PASSWORD = "postgres"  # Default PostgreSQL password

async def create_database():
    """Create the database if it doesn't exist"""
    try:
        # Connect to PostgreSQL server (default database)
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cursor.fetchone()
        
        if not exists:
            # Create database
            cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"✅ Created database: {DB_NAME}")
        else:
            print(f"✅ Database {DB_NAME} already exists")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        print("Make sure PostgreSQL is running on port 5433")
        return False
    
    return True

async def create_schema():
    """Create the database schema (tables)"""
    try:
        # Connect to the specific database
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        # Create tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                id SERIAL PRIMARY KEY,
                owner VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                full_name VARCHAR(511) NOT NULL UNIQUE,
                url VARCHAR(511) NOT NULL,
                default_branch VARCHAR(255) DEFAULT 'main',
                language VARCHAR(100),
                size INTEGER DEFAULT 0,
                stars INTEGER DEFAULT 0,
                forks INTEGER DEFAULT 0,
                analysis_status VARCHAR(50) DEFAULT 'pending',
                analysis_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        print("✅ Created repositories table")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id SERIAL PRIMARY KEY,
                repository_id INTEGER NOT NULL,
                analysis_type VARCHAR(100) NOT NULL,
                status VARCHAR(50) DEFAULT 'running',
                results JSONB,
                metrics JSONB,
                errors TEXT,
                duration INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        print("✅ Created analyses table")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id SERIAL PRIMARY KEY,
                repository_id INTEGER NOT NULL,
                path VARCHAR(1000) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                extension VARCHAR(50),
                language VARCHAR(100),
                size INTEGER DEFAULT 0,
                lines_of_code INTEGER DEFAULT 0,
                complexity INTEGER DEFAULT 0,
                quality_score INTEGER DEFAULT 0,
                analysis_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        print("✅ Created files table")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                id SERIAL PRIMARY KEY,
                repository_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                version VARCHAR(100),
                package_manager VARCHAR(50),
                dependency_type VARCHAR(50),
                vulnerabilities JSONB,
                license VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        print("✅ Created dependencies table")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS quality_metrics (
                id SERIAL PRIMARY KEY,
                repository_id INTEGER NOT NULL,
                metric_name VARCHAR(255) NOT NULL,
                metric_value VARCHAR(255),
                metric_type VARCHAR(100),
                threshold VARCHAR(100),
                status VARCHAR(50),
                details JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        print("✅ Created quality_metrics table")
        
        # Create indexes for better performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_analyses_repository_id ON analyses(repository_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_repository_id ON files(repository_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_repository_id ON dependencies(repository_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_quality_metrics_repository_id ON quality_metrics(repository_id);")
        print("✅ Created database indexes")
        
        await conn.close()
        print("✅ Database schema created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating schema: {e}")
        return False
    
    return True

async def test_connection():
    """Test the database connection"""
    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        
        # Test query
        result = await conn.fetchval("SELECT version();")
        print(f"✅ Database connection successful!")
        print(f"PostgreSQL version: {result}")
        
        # Count tables
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f"✅ Found {len(tables)} tables in the database")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("🚀 Setting up CodeAce AI database...")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"Database: {DB_NAME}")
    print(f"User: {DB_USER}")
    print("-" * 50)
    
    # Create database
    if not await create_database():
        return
    
    # Create schema
    if not await create_schema():
        return
    
    # Test connection
    if not await test_connection():
        return
    
    print("-" * 50)
    print("🎉 Database setup completed successfully!")
    print(f"You can now connect to: postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")

if __name__ == "__main__":
    asyncio.run(main())
