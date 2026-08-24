"""
PostgreSQL Database Setup Script for CodeTrace AI
This script sets up PostgreSQL with proper credentials and initializes all tables
"""

import asyncio
import asyncpg
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.config import settings
from database.connection import Base, engine
from database.models import Repository, Analysis, File, Dependency, QualityMetric
from database.enhanced_models import (
    GraphAnalysis, EnhancedGraphNode, EnhancedGraphEdge,
    CVSSVulnerability, SBOMDocument, SBOMComponent,
    SPDXDocument, SPDXPackage, SPDXRelationship,
    SecurityAssessment, LicenseCompliance
)

async def setup_postgresql():
    """Complete PostgreSQL setup for CodeTrace AI"""
    print("🔧 Setting up PostgreSQL for CodeTrace AI...")
    
    try:
        # Step 1: Test connection to PostgreSQL server
        print(f"📡 Testing connection to PostgreSQL server at {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        
        # Try connecting to the default 'postgres' database first
        server_url = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/postgres"
        
        try:
            conn = await asyncpg.connect(server_url)
            print("✅ Successfully connected to PostgreSQL server")
            
            # Step 2: Create database if it doesn't exist
            db_exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                settings.POSTGRES_DB
            )
            
            if not db_exists:
                print(f"🏗️ Creating database: {settings.POSTGRES_DB}")
                await conn.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
                print(f"✅ Database '{settings.POSTGRES_DB}' created successfully")
            else:
                print(f"✅ Database '{settings.POSTGRES_DB}' already exists")
            
            await conn.close()
            
        except asyncpg.InvalidPasswordError:
            print(f"❌ Authentication failed for user '{settings.POSTGRES_USER}'")
            print("💡 Please ensure PostgreSQL is running and credentials are correct")
            print(f"💡 Current settings: Host={settings.POSTGRES_HOST}, Port={settings.POSTGRES_PORT}, User={settings.POSTGRES_USER}")
            
            # Provide setup instructions
            print("\n🔧 PostgreSQL Setup Instructions:")
            print("1. Install PostgreSQL if not already installed")
            print("2. Start PostgreSQL service")
            print("3. Create a user and database:")
            print(f"   CREATE USER {settings.POSTGRES_USER} WITH PASSWORD '{settings.POSTGRES_PASSWORD}';")
            print(f"   CREATE DATABASE {settings.POSTGRES_DB} OWNER {settings.POSTGRES_USER};")
            print(f"   GRANT ALL PRIVILEGES ON DATABASE {settings.POSTGRES_DB} TO {settings.POSTGRES_USER};")
            
            # Offer to continue without database
            print("\n⚠️ Application can run without PostgreSQL for testing purposes")
            print("🔄 Repository data will not be persisted without database connection")
            return False
            
        except Exception as e:
            print(f"❌ Cannot connect to PostgreSQL: {e}")
            print("💡 Please ensure PostgreSQL is running and accessible")
            return False
        
        # Step 3: Create all database tables
        print("🏗️ Creating database tables...")
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ All database tables created successfully")
            
            # Step 4: Verify table creation
            app_db_url = settings.postgres_url
            app_conn = await asyncpg.connect(app_db_url)
            
            tables = await app_conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            
            print(f"📊 Created {len(tables)} tables:")
            for table in tables:
                print(f"   ✓ {table['table_name']}")
            
            await app_conn.close()
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            return False
        
        print("\n🎉 PostgreSQL setup completed successfully!")
        print(f"📊 Database: {settings.POSTGRES_DB}")
        print(f"🔗 Connection: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
        print("✅ Ready for repository analysis persistence")
        
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

async def test_database_operations():
    """Test basic database operations"""
    print("\n🧪 Testing database operations...")
    
    try:
        from services.repository_service import repository_service
        
        # Test repository creation
        test_repo_data = {
            'owner': 'test',
            'name': 'sample-repo',
            'full_name': 'test/sample-repo',
            'url': 'https://github.com/test/sample-repo',
            'default_branch': 'main',
            'language': 'Python',
            'size': 1000,
            'stars': 10,
            'forks': 2,
            'metadata': {'test': True}
        }
        
        print("📝 Testing repository creation...")
        repo = await repository_service.save_repository(test_repo_data)
        print(f"✅ Repository created with ID: {repo['id']}")
        
        # Test repository retrieval
        print("📖 Testing repository retrieval...")
        retrieved_repo = await repository_service.get_repository('test', 'sample-repo')
        print(f"✅ Repository retrieved: {retrieved_repo['full_name']}")
        
        # Test analysis result saving
        print("📊 Testing analysis result saving...")
        analysis_data = {
            'type': 'test',
            'results': {'test': 'data'},
            'metrics': {'score': 85.5},
            'duration': 30
        }
        
        analysis = await repository_service.save_analysis_result(repo['id'], analysis_data)
        print(f"✅ Analysis saved with ID: {analysis['id']}")
        
        print("\n🎉 Database operations test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database operations test failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("🚀 CodeTrace AI - PostgreSQL Database Setup")
    print("=" * 50)
    
    # Setup PostgreSQL
    setup_success = await setup_postgresql()
    
    if setup_success:
        # Test database operations
        test_success = await test_database_operations()
        
        if test_success:
            print("\n✅ PostgreSQL setup and testing completed successfully!")
            print("🔄 Repository analysis results will now be persisted to database")
        else:
            print("\n⚠️ Database setup completed but operations test failed")
            print("💡 Check database permissions and connection settings")
    else:
        print("\n❌ PostgreSQL setup failed")
        print("🔄 Application will run without persistence")
    
    print("\n" + "=" * 50)
    print("Setup complete. You can now start the CodeTrace AI server.")

if __name__ == "__main__":
    asyncio.run(main())
