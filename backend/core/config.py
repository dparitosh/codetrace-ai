"""Configuration for the local-first CodeTrace AI service."""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CodeTrace AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8009
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"])
    GITLAB_ALLOWED_HOSTS: List[str] = Field(default=["gitlab.com"], description="Allowed GitLab hosts for project cloning")
    UPLOAD_DIR: str = "./data/uploads"
    TEMP_DIR: str = "./temp"
    LOG_DIR: str = "./logs"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    def create_directories(self) -> None:
        for directory in (self.UPLOAD_DIR, self.TEMP_DIR, self.LOG_DIR):
            Path(directory).mkdir(parents=True, exist_ok=True)


settings = Settings()
DEBUG = settings.DEBUG
