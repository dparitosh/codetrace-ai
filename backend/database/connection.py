"""
Database connection setup for PostgreSQL with enhanced fallback capabilities
"""

import asyncio
import logging
import databases
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError
from typing import Optional, Dict, Any, List
from core.config import settings

logger = logging.getLogger(__name__)


class DatabaseFallback:
    """In-memory fallback database for when PostgreSQL is unavailable"""

    def __init__(self):
        self.repositories = {}
        self.analyses = {}
        self.users = {}
        self.logger = logging.getLogger("database_fallback")

    def store_repository(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store repository data in memory"""
        key = f"{repo_data.get('owner')}/{repo_data.get('name')}"
        self.repositories[key] = repo_data
        self.logger.info(f"Stored repository in fallback: {key}")
        return repo_data

    def get_repository(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Retrieve repository data from memory"""
        key = f"{owner}/{repo}"
        return self.repositories.get(key)

    def store_analysis(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store analysis data in memory"""
        key = f"{analysis_data.get('repository_id')}:{analysis_data.get('id')}"
        self.analyses[key] = analysis_data
        self.logger.info(f"Stored analysis in fallback: {key}")
        return analysis_data

    def get_analyses(self, repository_id: str) -> List[Dict[str, Any]]:
        """Get all analyses for a repository"""
        return [
            analysis
            for key, analysis in self.analyses.items()
            if key.startswith(f"{repository_id}:")
        ]


class EnhancedDatabase:
    """Enhanced database connection with fallback capabilities"""

    def __init__(self):
        self.database = None
        self.engine = None
        self.fallback = DatabaseFallback()
        self.is_connected = False
        self.use_fallback = False
        self.connection_attempts = 0
        self.max_connection_attempts = 3

    async def initialize(self):
        """Initialize database connection with fallback"""
        try:
            # Try to connect to PostgreSQL
            self.database = databases.Database(settings.postgres_url)
            await self.database.connect()

            # Test connection
            await self.database.execute("SELECT 1")

            self.is_connected = True
            self.use_fallback = False
            logger.info("Successfully connected to PostgreSQL database")

        except Exception as e:
            self.connection_attempts += 1
            logger.error(
                f"Failed to connect to PostgreSQL (attempt {self.connection_attempts}/{self.max_connection_attempts}): {e}"
            )

            if self.connection_attempts >= self.max_connection_attempts:
                logger.warning(
                    "Maximum connection attempts reached. Switching to fallback mode."
                )
                self.use_fallback = True
                self.is_connected = False
            else:
                # Retry connection after delay
                await asyncio.sleep(2)
                await self.initialize()

    async def execute(self, query: str, values: Optional[Dict] = None):
        """Execute query with fallback handling"""
        if self.use_fallback:
            logger.debug(f"Database in fallback mode, skipping query: {query[:50]}...")
            return None

        try:
            if self.database and self.is_connected:
                return await self.database.execute(query, values)
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            await self._handle_connection_error()
            return None

    async def fetch_all(self, query: str, values: Optional[Dict] = None):
        """Fetch all results with fallback handling"""
        if self.use_fallback:
            logger.debug(
                f"Database in fallback mode, returning empty results for: {query[:50]}..."
            )
            return []

        try:
            if self.database and self.is_connected:
                return await self.database.fetch_all(query, values)
        except Exception as e:
            logger.error(f"Database fetch failed: {e}")
            await self._handle_connection_error()
            return []

    async def fetch_one(self, query: str, values: Optional[Dict] = None):
        """Fetch one result with fallback handling"""
        if self.use_fallback:
            logger.debug(
                f"Database in fallback mode, returning None for: {query[:50]}..."
            )
            return None

        try:
            if self.database and self.is_connected:
                return await self.database.fetch_one(query, values)
        except Exception as e:
            logger.error(f"Database fetch one failed: {e}")
            await self._handle_connection_error()
            return None

    async def _handle_connection_error(self):
        """Handle database connection errors"""
        self.is_connected = False
        logger.warning("Database connection lost. Attempting to reconnect...")

        try:
            await self.initialize()
        except Exception as e:
            logger.error(f"Failed to reconnect to database: {e}")
            if not self.use_fallback:
                logger.warning(
                    "Switching to fallback mode due to persistent connection issues"
                )
                self.use_fallback = True

    async def disconnect(self):
        """Disconnect from database"""
        if self.database and self.is_connected:
            try:
                await self.database.disconnect()
                logger.info("Disconnected from PostgreSQL database")
            except Exception as e:
                logger.error(f"Error disconnecting from database: {e}")

        self.is_connected = False

    def get_status(self) -> Dict[str, Any]:
        """Get database connection status"""
        return {
            "connected": self.is_connected,
            "using_fallback": self.use_fallback,
            "connection_attempts": self.connection_attempts,
            "database_url": (
                settings.postgres_url if not self.use_fallback else "fallback"
            ),
            "fallback_data": {
                "repositories": len(self.fallback.repositories),
                "analyses": len(self.fallback.analyses),
            },
        }


# Global database instance
enhanced_db = EnhancedDatabase()

# Legacy compatibility
DATABASE_URL = settings.postgres_url
database = enhanced_db  # For backward compatibility
engine = (
    sqlalchemy.create_engine(DATABASE_URL) if not enhanced_db.use_fallback else None
)
metadata = sqlalchemy.MetaData()
Base = declarative_base()


async def connect_db():
    """Connect to the database with fallback support"""
    await enhanced_db.initialize()
    status = enhanced_db.get_status()
    if status["connected"]:
        logger.info(f"Connected to PostgreSQL database: {settings.POSTGRES_DB}")
    elif status["using_fallback"]:
        logger.warning("Running in database fallback mode - data will not be persisted")
    else:
        logger.error("Database connection failed and fallback not enabled")


async def disconnect_db():
    """Disconnect from the database"""
    await enhanced_db.disconnect()


def create_tables():
    """Create all tables if database is available"""
    if not enhanced_db.use_fallback and engine:
        try:
            metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
    else:
        logger.info("Skipping table creation - using fallback mode")


def get_database_status() -> Dict[str, Any]:
    """Get current database status"""
    return enhanced_db.get_status()
