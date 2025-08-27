"""
CodeTrace AI - Enhanced Logging Configuration
Provides structured logging with performance tracking and error context
"""

import logging
import logging.config
import sys
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path


class PerformanceLogger:
    """Context manager for tracking operation performance"""

    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting operation: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type:
            self.logger.error(
                f"Operation failed: {self.operation} (duration: {duration:.2f}s)"
            )
            self.logger.error(f"Error: {exc_val}")
        else:
            self.logger.info(
                f"Operation completed: {self.operation} (duration: {duration:.2f}s)"
            )


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""

    def format(self, record):
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add performance info if available
        if hasattr(record, "duration"):
            log_entry["duration_ms"] = round(record.duration * 1000, 2)

        # Add error context for exceptions
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        return f"{log_entry['timestamp']} | {log_entry['level']:<8} | {log_entry['logger']:<20} | {log_entry['message']}"


class GitHubAPILogger(logging.LoggerAdapter):
    """Specialized logger for GitHub API operations"""

    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})

    def api_request(
        self,
        method: str,
        endpoint: str,
        status_code: Optional[int] = None,
        duration: Optional[float] = None,
        **kwargs,
    ):
        """Log GitHub API request"""
        extra = {
            "api_method": method,
            "api_endpoint": endpoint,
            "api_status": status_code,
            "duration": duration,
        }
        extra.update(kwargs)

        if status_code and status_code >= 400:
            self.error(
                f"GitHub API {method} {endpoint} failed with {status_code}", extra=extra
            )
        else:
            self.info(f"GitHub API {method} {endpoint} completed", extra=extra)


def setup_logging(log_level: str = "INFO", log_dir: str = "logs"):
    """
    Setup application logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Configure logging level
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )

    simple_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    # File handler for all logs
    log_file = log_path / f"codeace_ai_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Error handler for critical issues
    error_file = log_path / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_file, maxBytes=5 * 1024 * 1024, backupCount=3  # 5MB
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)

    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    logging.info("Logging configuration initialized")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
