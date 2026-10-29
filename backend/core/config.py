"""Configuration for the local-first CodeTrace AI service."""

import json
import ipaddress
from pathlib import Path
from typing import List, Optional, Literal
from urllib.parse import quote, urlsplit
from core.connection_models import ManagedRepository, OSLCProvider, PipelineProvider, connection_url, ai_connection_url

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = json.loads((PROJECT_ROOT / 'config/defaults.json').read_text(encoding='utf-8'))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / '.env', PROJECT_ROOT / '.env.local'),
        env_file_encoding='utf-8', case_sensitive=True, extra='ignore', populate_by_name=True,
        hide_input_in_errors=True,
    )
    APP_NAME: str = "CodeTrace AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    POSTGRES_HOST: str = Field(default='127.0.0.1', min_length=1)
    POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
    POSTGRES_DB: str = Field(default='codetrace_ai', pattern=r'^[A-Za-z_][A-Za-z0-9_]{0,62}$')
    POSTGRES_USER: str = Field(default='codetrace', min_length=1)
    POSTGRES_PASSWORD: str = Field(default='', repr=False)
    POSTGRES_CONNECT_TIMEOUT_SECONDS: int = Field(default=10, ge=1, le=120)
    HOST: str = Field(default=DEFAULTS['HOST'], min_length=1)
    PORT: int = Field(default=DEFAULTS['BACKEND_PORT'], ge=1, le=65535,
                      validation_alias=AliasChoices('BACKEND_PORT', 'PORT'))
    FRONTEND_PORT: int = Field(default=DEFAULTS['FRONTEND_PORT'], ge=1, le=65535)
    CORS_ORIGINS: Optional[List[str]] = None
    GITLAB_ALLOWED_HOSTS: List[str] = Field(default=["gitlab.com"], description="Allowed GitLab hosts for project cloning")
    MAX_LOCAL_FILES: int = Field(default=DEFAULTS['MAX_LOCAL_FILES'], ge=1)
    MAX_LOCAL_PAYLOAD_BYTES: int = Field(default=DEFAULTS['MAX_LOCAL_PAYLOAD_BYTES'], ge=1)
    MAX_SOURCE_FILE_BYTES: int = Field(default=DEFAULTS['MAX_SOURCE_FILE_BYTES'], ge=1)
    SECURITY_MAX_FINDINGS: int = Field(default=DEFAULTS['SECURITY_MAX_FINDINGS'], ge=1)
    GITLAB_CLONE_TIMEOUT_SECONDS: int = Field(default=DEFAULTS['GITLAB_CLONE_TIMEOUT_SECONDS'], ge=1)
    GRAPH_PREVIEW_NODES: int = Field(default=DEFAULTS['GRAPH_PREVIEW_NODES'], ge=1)
    GRAPH_PREVIEW_EDGES: int = Field(default=DEFAULTS['GRAPH_PREVIEW_EDGES'], ge=1)
    MAX_TRACE_MANIFEST_BYTES: int = Field(default=DEFAULTS['MAX_TRACE_MANIFEST_BYTES'], ge=1)
    REQUEST_TIMEOUT_SECONDS: int = Field(default=DEFAULTS['REQUEST_TIMEOUT_SECONDS'], ge=1)
    SESSION_IDLE_SECONDS: int = Field(default=DEFAULTS['SESSION_IDLE_SECONDS'], ge=1)
    SESSION_MAX_SECONDS: int = Field(default=DEFAULTS['SESSION_MAX_SECONDS'], ge=1)
    MAX_SESSIONS: int = Field(default=DEFAULTS['MAX_SESSIONS'], ge=1)
    SESSION_STORE: Literal['memory', 'sqlite'] = 'memory'
    SESSION_DB_PATH: Path = PROJECT_ROOT / 'data/reviews.sqlite3'
    CHANGE_DB_PATH: Path = PROJECT_ROOT / 'data/changes.sqlite3'
    CHANGE_MAX_CASES: int = Field(default=128, ge=1)
    CHANGE_MAX_BYTES: int = Field(default=50000000, ge=10000)
    MAX_REVIEWS_PER_SESSION: int = Field(default=DEFAULTS['MAX_REVIEWS_PER_SESSION'], ge=1)
    MAX_REVIEW_STORAGE_BYTES: int = Field(default=DEFAULTS['MAX_REVIEW_STORAGE_BYTES'], ge=1)
    MAX_CONCURRENT_ANALYSES: int = Field(default=DEFAULTS['MAX_CONCURRENT_ANALYSES'], ge=1)
    MAX_GRAPH_NODES: int = Field(default=DEFAULTS['MAX_GRAPH_NODES'], ge=1)
    MAX_GRAPH_EDGES: int = Field(default=DEFAULTS['MAX_GRAPH_EDGES'], ge=1)
    CONTROL_REQUEST_TIMEOUT_SECONDS: int = Field(default=DEFAULTS['CONTROL_REQUEST_TIMEOUT_SECONDS'], ge=1)
    REVIEW_PREVIEW_ITEMS: int = Field(default=DEFAULTS['REVIEW_PREVIEW_ITEMS'], ge=1)
    STARTUP_TIMEOUT_SECONDS: int = Field(default=DEFAULTS['STARTUP_TIMEOUT_SECONDS'], ge=1)
    SOURCE_EXTENSIONS: Optional[List[str]] = None
    SOURCE_EXCLUDES: Optional[List[str]] = None
    UPLOAD_DIR: Path = PROJECT_ROOT / 'data/uploads'
    TEMP_DIR: Path = PROJECT_ROOT / 'temp'
    LOG_DIR: Path = PROJECT_ROOT / 'logs'
    SOURCE_FOLDER: Path = PROJECT_ROOT
    MANAGED_REPOSITORIES: Optional[List[ManagedRepository]] = None
    OSLC_PROVIDERS: List[OSLCProvider] = Field(default_factory=list)
    CI_MAX_PAGES: int = Field(default=5, ge=1, le=100)
    CI_MAX_RUNS: int = Field(default=100, ge=1, le=2000)
    CI_PROVIDERS: List[PipelineProvider] = Field(default_factory=list)
    OSLC_TIMEOUT_SECONDS: int = Field(default=20, ge=1, le=120)
    OSLC_MAX_PAGES: int = Field(default=10, ge=1, le=100)
    OSLC_MAX_RESOURCES: int = Field(default=500, ge=1, le=5000)
    OSLC_MAX_RESPONSE_BYTES: int = Field(default=2000000, ge=1)
    SBOM_MAX_BYTES: int = Field(default=10000000, ge=1)
    SBOM_MAX_COMPONENTS: int = Field(default=2000, ge=1, le=10000)
    VULNERABILITY_PROVIDER: Literal['disabled', 'osv-compatible'] = 'disabled'
    VULNERABILITY_REQUIRE_HTTPS: bool = False
    VULNERABILITY_API_URL: str = ''
    VULNERABILITY_TOKEN_ENV: str = Field(default='CODETRACE_VULNERABILITY_TOKEN', pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    VULNERABILITY_KEY_HEADER: Literal['Authorization', 'api-key', 'Ocp-Apim-Subscription-Key'] = 'Authorization'
    VULNERABILITY_TIMEOUT_SECONDS: int = Field(default=20, ge=1, le=120)
    VULNERABILITY_MAX_RESPONSE_BYTES: int = Field(default=2000000, ge=1000)
    VULNERABILITY_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)
    TRS_INCREMENTAL: bool = True
    TRS_CACHE_PATH: Path = PROJECT_ROOT / 'data/trs.sqlite3'
    TRS_CACHE_EVENTS: int = Field(default=1000, ge=1, le=10000)
    TRS_CACHE_MAX_BYTES: int = Field(default=20000000, ge=1)
    AI_PROVIDER: Literal['disabled', 'ollama', 'openai-compatible'] = 'disabled'
    AI_REQUIRE_HTTPS: bool = False
    AI_DISCOVERY_ENABLED: bool = True
    AI_BASE_URL: str = 'http://127.0.0.1:11434'
    AI_MODEL: str = ''
    AI_TOKEN_ENV: str = 'CODETRACE_AI_TOKEN'
    AI_TIMEOUT_SECONDS: int = Field(default=45, ge=1, le=300)
    AI_CONTEXT_NODES: int = Field(default=35, ge=1, le=100)
    AI_CONTEXT_RELATIONS: int = Field(default=80, ge=1, le=1000)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=700, ge=1, le=8192)
    AI_MAX_RESPONSE_BYTES: int = Field(default=2000000, ge=1)
    AI_MAX_ANSWER_CHARACTERS: int = Field(default=10000, ge=1)
    AI_EMBEDDING_MODEL: str = 'nomic-embed-text'
    AI_ALLOWED_BASE_URLS: List[str] = Field(default_factory=list)
    AI_KEY_HEADER: Literal['Authorization', 'api-key', 'Ocp-Apim-Subscription-Key'] = 'Authorization'
    AI_AGENT_MAX_STEPS: int = Field(default=5, ge=1, le=12)
    AI_AGENT_DEADLINE_SECONDS: int = Field(default=120, ge=5, le=600)
    AI_CONTEXT_MAX_BYTES: int = Field(default=120000, ge=4096, le=1000000)
    AI_EMBEDDING_MAX_NODES: int = Field(default=300, ge=1, le=2000)
    AI_EMBEDDING_BATCH_SIZE: int = Field(default=24, ge=1, le=64)
    WORKSPACE_RENDER_NODES: int = Field(default=400, ge=10, le=2000)
    WORKSPACE_RENDER_EDGES: int = Field(default=1000, ge=10, le=5000)
    OSLC_PUBLIC_BASE_URL: Optional[str] = None
    OSLC_DB_PATH: Path = PROJECT_ROOT / 'data/oslc.sqlite3'
    OSLC_SERVER_TOKEN_ENV: str = 'CODETRACE_OSLC_TOKEN'
    OSLC_SERVER_WRITE_TOKEN_ENV: str = 'CODETRACE_OSLC_WRITE_TOKEN'
    OSLC_SERVER_ALLOW_WRITES: bool = False
    OSLC_SERVER_MAX_RESOURCES: int = Field(default=50000, ge=1)
    OSLC_SERVER_MAX_EVENTS: int = Field(default=100000, ge=1)
    OSLC_SERVER_MAX_BYTES: int = Field(default=100000000, ge=1)
    OSLC_SERVER_MAX_PROPOSALS: int = Field(default=1000, ge=1)

    @field_validator('HOST')
    @classmethod
    def bare_bind_host(cls, value):
        message = 'Use a hostname or IP address only, without http://, https://, a port, path or credentials'
        if any(char.isspace() for char in value) or any(char in value for char in '/\\?#@'):
            raise ValueError(message)
        if ':' in value:
            host = value[1:-1] if value.startswith('[') and value.endswith(']') else value
            try:
                ipaddress.IPv6Address(host)
            except ValueError:
                raise ValueError(message) from None
            return host
        if '[' in value or ']' in value:
            raise ValueError(message)
        return value

    @field_validator('AI_BASE_URL', 'OSLC_PUBLIC_BASE_URL')
    @classmethod
    def named_endpoint(cls, value, info):
        if info.field_name == 'OSLC_PUBLIC_BASE_URL' and value == '':
            return None
        return (ai_connection_url(value, info.data.get('AI_REQUIRE_HTTPS', False))
                if info.field_name == 'AI_BASE_URL' else connection_url(value))

    @field_validator('AI_ALLOWED_BASE_URLS')
    @classmethod
    def named_allowed_endpoints(cls, values, info):
        for index, value in enumerate(values):
            try:
                ai_connection_url(value, info.data.get('AI_REQUIRE_HTTPS', False))
            except ValueError as error:
                raise ValueError(f'Entry {index}: {error}') from None
        return values

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # Normalize aliases within each source before sources are merged. Otherwise
        # a file's BACKEND_PORT can incorrectly beat the process's legacy PORT.
        def normalized(source):
            def read():
                values = source()
                if 'PORT' in values:
                    values.setdefault('BACKEND_PORT', values.pop('PORT'))
                return values
            return read
        return tuple(normalized(source) for source in (init_settings, env_settings, dotenv_settings, file_secret_settings))

    @model_validator(mode='after')
    def resolve_local_settings(self):
        if self.VULNERABILITY_API_URL:
            connection_url(self.VULNERABILITY_API_URL, require_https=False)
            parsed_advisory = urlsplit(self.VULNERABILITY_API_URL)
            if parsed_advisory.query or any(ord(c) < 33 for c in self.VULNERABILITY_API_URL) or '\\' in self.VULNERABILITY_API_URL:
                raise ValueError('VULNERABILITY_API_URL must not contain query parameters, whitespace or backslashes')
            if self.VULNERABILITY_REQUIRE_HTTPS and parsed_advisory.scheme != 'https':
                raise ValueError('VULNERABILITY_REQUIRE_HTTPS=true requires an HTTPS advisory endpoint')
        if self.VULNERABILITY_PROVIDER != 'disabled' and not self.VULNERABILITY_API_URL:
            raise ValueError('An enabled vulnerability provider requires VULNERABILITY_API_URL')
        self.SOURCE_FOLDER = (self.SOURCE_FOLDER if self.SOURCE_FOLDER.is_absolute()
                              else PROJECT_ROOT / self.SOURCE_FOLDER).resolve()
        if self.MANAGED_REPOSITORIES is None:
            self.MANAGED_REPOSITORIES = [ManagedRepository(
                id='workspace', label='Configured source folder', kind='local', path=str(self.SOURCE_FOLDER))]
        self.OSLC_PUBLIC_BASE_URL = self.OSLC_PUBLIC_BASE_URL or f'http://{self.browser_host}:{self.PORT}/oslc'
        connection_url(self.OSLC_PUBLIC_BASE_URL)
        repository_ids = {item.id for item in self.MANAGED_REPOSITORIES}
        for values in (self.MANAGED_REPOSITORIES, self.OSLC_PROVIDERS, self.CI_PROVIDERS):
            if len({item.id for item in values}) != len(values):
                raise ValueError('Connection identifiers must be unique within each catalog')
        if any(set(provider.repository_ids) - repository_ids for provider in self.OSLC_PROVIDERS):
            raise ValueError('OSLC provider references an unknown managed repository')
        if any(provider.repository_id not in repository_ids for provider in self.CI_PROVIDERS):
            raise ValueError('Pipeline provider references an unknown managed repository')
        if self.AI_PROVIDER != 'disabled' and not self.AI_MODEL.strip():
            raise ValueError('An enabled AI provider requires AI_MODEL')
        if self.PORT == self.FRONTEND_PORT:
            raise ValueError('BACKEND_PORT and FRONTEND_PORT must differ')
        if self.MAX_SOURCE_FILE_BYTES > self.MAX_LOCAL_PAYLOAD_BYTES:
            raise ValueError('MAX_SOURCE_FILE_BYTES cannot exceed MAX_LOCAL_PAYLOAD_BYTES')
        if self.CORS_ORIGINS is None:
            self.CORS_ORIGINS = list(dict.fromkeys([
                self.frontend_url, f'http://localhost:{self.FRONTEND_PORT}',
                f'http://127.0.0.1:{self.FRONTEND_PORT}',
            ]))
        for name in ('UPLOAD_DIR', 'TEMP_DIR', 'LOG_DIR', 'OSLC_DB_PATH', 'SESSION_DB_PATH', 'TRS_CACHE_PATH', 'CHANGE_DB_PATH'):
            value = getattr(self, name)
            if not value.is_absolute():
                setattr(self, name, PROJECT_ROOT / value)
        return self

    @property
    def postgres_url(self):
        host = f'[{self.POSTGRES_HOST}]' if ':' in self.POSTGRES_HOST else self.POSTGRES_HOST
        return f'postgresql://{quote(self.POSTGRES_USER, safe="")}:{quote(self.POSTGRES_PASSWORD, safe="")}@{host}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'

    @property
    def browser_host(self):
        host = '127.0.0.1' if self.HOST in {'0.0.0.0', '::'} else self.HOST
        return f'[{host}]' if ':' in host else host

    @property
    def frontend_url(self):
        return f'http://{self.browser_host}:{self.FRONTEND_PORT}'

    def create_directories(self) -> None:
        for directory in (self.UPLOAD_DIR, self.TEMP_DIR, self.LOG_DIR):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
DEBUG = settings.DEBUG
