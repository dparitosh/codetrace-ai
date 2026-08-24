"""
CodeTrace AI - Core Configuration Module
Centralized configuration management for the application
"""

import os
import sys
import logging
from typing import List, Optional, Dict, Any
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from pathlib import Path

# Configure logging for configuration validation
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration validation fails"""

    pass


class Settings(BaseSettings):
    """Application settings and configuration"""

    # Application
    APP_NAME: str = "CodeTrace AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")

    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8009, env="PORT")

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:5173",
            "http://localhost:8080",
            "https://codetrace.ai",
        ],
        env="CORS_ORIGINS",
    )

    # GitHub Integration
    GITHUB_TOKEN: Optional[str] = Field(default=None, env="GITHUB_TOKEN")
    GITHUB_APP_ID: Optional[str] = Field(default=None, env="GITHUB_APP_ID")
    GITHUB_APP_PRIVATE_KEY: Optional[str] = Field(
        default=None, env="GITHUB_APP_PRIVATE_KEY"
    )
    GITHUB_WEBHOOK_SECRET: Optional[str] = Field(
        default=None, env="GITHUB_WEBHOOK_SECRET"
    )
    GITHUB_INSTALLATION_ID: Optional[str] = Field(
        default=None, env="GITHUB_INSTALLATION_ID"
    )

    # GitHub API Configuration
    GITHUB_API_FALLBACK: bool = Field(default=False, env="GITHUB_API_FALLBACK")
    USE_MOCK_DATA: bool = Field(default=False, env="USE_MOCK_DATA")
    FORCE_FRESH_DATA: bool = Field(default=True, env="FORCE_FRESH_DATA")
    GITHUB_API_TIMEOUT: int = Field(default=180, env="GITHUB_API_TIMEOUT")

    # Database - PostgreSQL
    POSTGRES_HOST: str = Field(default="localhost", env="DB_HOST")
    POSTGRES_PORT: int = Field(default=5433, env="DB_PORT")
    POSTGRES_DB: str = Field(default="codeace_ai", env="DB_NAME")
    POSTGRES_USER: str = Field(default="postgres", env="DB_USER")
    POSTGRES_PASSWORD: str = Field(
        default="postgres", env="DB_PASSWORD"
    )  # Default for testing

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Database - Neo4j
    NEO4J_URI: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field(default="neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field(
        default="neo4j", env="NEO4J_PASSWORD"
    )  # Default for testing

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")

    # Security
    JWT_SECRET: str = Field(
        default="jwt-secret-for-testing-only", env="JWT_SECRET"
    )  # Default for testing
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION: int = Field(
        default=7 * 24 * 60 * 60, env="JWT_EXPIRATION"
    )  # 7 days

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=60, env="RATE_LIMIT_WINDOW")  # seconds

    # Analysis Configuration
    MAX_REPOSITORY_SIZE: str = Field(default="500MB", env="MAX_REPOSITORY_SIZE")
    MAX_FILES_PER_REPO: int = Field(default=10000, env="MAX_FILES_PER_REPO")
    ANALYSIS_TIMEOUT: int = Field(default=600, env="ANALYSIS_TIMEOUT")  # seconds

    # Real-Data Configuration
    ENABLE_REAL_DATA_ONLY: bool = Field(default=True, env="ENABLE_REAL_DATA_ONLY")
    DISABLE_ALL_FALLBACKS: bool = Field(default=True, env="DISABLE_ALL_FALLBACKS")

    # Quality Assessment
    ENABLE_SECURITY_SCAN: bool = Field(default=True, env="ENABLE_SECURITY_SCAN")
    ENABLE_DEPENDENCY_CHECK: bool = Field(default=True, env="ENABLE_DEPENDENCY_CHECK")
    ENABLE_CODE_QUALITY: bool = Field(default=True, env="ENABLE_CODE_QUALITY")
    ENABLE_PERFORMANCE_ANALYSIS: bool = Field(
        default=True, env="ENABLE_PERFORMANCE_ANALYSIS"
    )

    # Storage
    UPLOAD_DIR: str = Field(default="/app/data/uploads", env="UPLOAD_DIR")
    TEMP_DIR: str = Field(default="/app/temp", env="TEMP_DIR")
    LOG_DIR: str = Field(default="/app/logs", env="LOG_DIR")

    # Cache
    CACHE_TTL: int = Field(default=0, env="CACHE_TTL")  # seconds - 0 means no caching
    CACHE_MAX_SIZE: int = Field(default=1000, env="CACHE_MAX_SIZE")

    # Feature Flags
    ENABLE_AUTH: bool = Field(default=False, env="ENABLE_AUTH")
    ENABLE_ANALYTICS: bool = Field(default=True, env="ENABLE_ANALYTICS")
    ENABLE_CACHING: bool = Field(
        default=False, env="ENABLE_CACHING"
    )  # Disabled for real data
    ENABLE_WEBHOOKS: bool = Field(default=True, env="ENABLE_WEBHOOKS")
    ENABLE_MONITORING: bool = Field(default=False, env="ENABLE_MONITORING")

    # External Services
    SLACK_WEBHOOK_URL: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    DISCORD_WEBHOOK_URL: Optional[str] = Field(default=None, env="DISCORD_WEBHOOK_URL")
    EMAIL_SERVICE_API_KEY: Optional[str] = Field(
        default=None, env="EMAIL_SERVICE_API_KEY"
    )

    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    DATADOG_API_KEY: Optional[str] = Field(default=None, env="DATADOG_API_KEY")
    PROMETHEUS_ENABLED: bool = Field(default=False, env="PROMETHEUS_ENABLED")

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

    def create_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [self.UPLOAD_DIR, self.TEMP_DIR, self.LOG_DIR]
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def validate_configuration(self) -> Dict[str, Any]:
        """Validate configuration and return validation report"""
        issues = []
        warnings = []

        # Critical validations
        if not self.GITHUB_TOKEN:
            issues.append("GITHUB_TOKEN is required for GitHub API access")

        # Database validation
        try:
            if self.POSTGRES_PASSWORD == "postgres":
                warnings.append(
                    "Using default PostgreSQL password - not recommended for production"
                )
        except Exception:
            issues.append("PostgreSQL configuration is invalid")

        # Port validation
        if not (1024 <= self.PORT <= 65535):
            issues.append(f"PORT {self.PORT} is outside valid range (1024-65535)")

        # Timeout validation
        if self.ANALYSIS_TIMEOUT > 1800:  # 30 minutes
            warnings.append(f"ANALYSIS_TIMEOUT ({self.ANALYSIS_TIMEOUT}s) is very high")

        # Security validation
        if self.JWT_SECRET == "jwt-secret-for-testing-only":
            warnings.append("Using default JWT secret - change for production")

        # Performance validation
        if self.MAX_FILES_PER_REPO > 50000:
            warnings.append(
                f"MAX_FILES_PER_REPO ({self.MAX_FILES_PER_REPO}) may cause performance issues"
            )

        validation_report = {
            "status": "valid" if not issues else "invalid",
            "critical_issues": issues,
            "warnings": warnings,
            "timestamp": os.environ.get("CONFIG_VALIDATION_TIME", "unknown"),
        }

        # Log validation results
        if issues:
            logger.error(
                f"Configuration validation failed: {len(issues)} critical issues"
            )
            for issue in issues:
                logger.error(f"  - {issue}")

        if warnings:
            logger.warning(f"Configuration warnings: {len(warnings)} warnings")
            for warning in warnings:
                logger.warning(f"  - {warning}")

        if not issues and not warnings:
            logger.info("Configuration validation passed - no issues found")

        return validation_report

    def get_safe_config(self) -> Dict[str, Any]:
        """Get configuration without sensitive values for logging"""
        safe_config = {}
        for key, value in self.dict().items():
            if any(
                sensitive in key.lower()
                for sensitive in ["password", "secret", "key", "token"]
            ):
                safe_config[key] = "[REDACTED]" if value else None
            else:
                safe_config[key] = value
        return safe_config


# Global settings instance
settings = Settings()

# Validate configuration on startup
validation_report = settings.validate_configuration()
if validation_report["status"] == "invalid":
    logger.error(
        "Configuration validation failed. Application may not function correctly."
    )
    logger.error(f"Critical issues: {validation_report['critical_issues']}")
else:
    logger.info("Configuration validation passed")

# Create directories on import
settings.create_directories()

# Export commonly used settings
DATABASE_URL = settings.postgres_url
GITHUB_TOKEN = settings.GITHUB_TOKEN
DEBUG = settings.DEBUG
