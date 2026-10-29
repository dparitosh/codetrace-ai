"""Central administrator-owned connection definitions, never browser-supplied URLs."""
from typing import Literal, Optional
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Connection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[A-Za-z0-9_-]+$', min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)


def connection_url(value, require_https=True):
    if value is None:
        return value
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError('Use a valid HTTP(S) endpoint with a port between 1 and 65535') from None
    if port == 0:
        raise ValueError('Use a valid HTTP(S) endpoint with a port between 1 and 65535')
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Use an HTTP(S) endpoint without embedded credentials or fragment')
    if require_https and parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Remote endpoints must use HTTPS')
    if any(word in parsed.query.lower() for word in ('token=', 'password=', 'secret=')):
        raise ValueError('Credentials belong in a named server environment variable')
    return value


def ai_connection_url(value, require_https=False):
    value = connection_url(value, require_https=False)
    if value is not None and require_https and urlsplit(value).scheme != 'https':
        raise ValueError('AI_REQUIRE_HTTPS=true requires an HTTPS AI endpoint; set false to allow HTTP')
    return value


class ManagedRepository(Connection):
    kind: Literal['local', 'git'] = 'local'
    path: Optional[str] = None
    url: Optional[str] = None
    ref: Optional[str] = Field(default=None, max_length=200)
    uri: Optional[str] = None
    manifest_path: Optional[str] = None
    token_env: Optional[str] = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    sbom_path: Optional[str] = None
    sbom_lockfiles: list[str] = Field(default_factory=lambda: ['package-lock.json', 'frontend/package-lock.json'], max_length=20)

    @field_validator('url')
    @classmethod
    def safe_url(cls, value):
        return connection_url(value)

    @model_validator(mode='after')
    def valid_source(self):
        if self.kind == 'local' and not self.path:
            raise ValueError('A local repository requires path')
        if self.kind == 'git' and not self.url:
            raise ValueError('A git repository requires url')
        return self


class OSLCProvider(Connection):
    product: Literal['generic', 'polarion', 'codebeamer'] = 'generic'
    domain: Literal['AM', 'RM', 'CM', 'QM', 'TRS']
    endpoint: Optional[str] = None
    allowed_base_url: Optional[str] = None
    file_path: Optional[str] = None
    token_env: Optional[str] = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    repository_ids: list[str] = Field(default_factory=list)
    configuration_uri: Optional[str] = None
    discovery_url: Optional[str] = None
    auth_type: Literal['none', 'bearer', 'basic'] = 'bearer'
    username_env: Optional[str] = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    password_env: Optional[str] = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    allow_writes: bool = False
    write_content_type: Literal['application/rdf+xml', 'text/turtle'] = 'application/rdf+xml'

    @field_validator('endpoint', 'allowed_base_url', 'discovery_url')
    @classmethod
    def safe_url(cls, value):
        return connection_url(value)

    @model_validator(mode='after')
    def valid_provider(self):
        if bool(self.endpoint) == bool(self.file_path):
            raise ValueError('Provide exactly one of endpoint or file_path')
        if self.endpoint and not self.allowed_base_url:
            raise ValueError('Network OSLC providers require an allowed_base_url for linked pages/resources')
        if self.auth_type == 'basic' and (not self.username_env or not self.password_env):
            raise ValueError('Basic authentication requires username_env and password_env')
        if self.allow_writes and not self.endpoint:
            raise ValueError('File providers cannot accept remote writes')
        return self


class PipelineProvider(Connection):
    platform: Literal['gitlab']
    endpoint: str
    token_env: Optional[str] = Field(default=None, pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')
    repository_id: str

    @field_validator('endpoint')
    @classmethod
    def safe_url(cls, value):
        return connection_url(value)
