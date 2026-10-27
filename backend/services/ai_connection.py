"""Session-owned Ollama REST configuration and bounded, secret-free transport."""
import json
import math
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from typing import Literal
from core.config import settings
from core.connection_models import ai_connection_url
from services.oslc_service import server_secret
from services.agent_configuration import AgentConfiguration, AgentId, ToolConfiguration, ToolId


def normalize_base(value):
    ai_connection_url(value, settings.AI_REQUIRE_HTTPS)
    url = urlsplit(value.strip())
    if (url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.port == 0 or '\\' in value
            or any(ord(char) < 33 for char in value)):
        raise ValueError('Use an HTTP(S) Ollama URL without credentials, query or fragment')
    path = url.path.rstrip('/')
    for suffix in ('/api/chat', '/api/generate', '/api/tags', '/api/embed', '/api/embeddings', '/api'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    if '%' in path or any(part in {'.', '..'} for part in path.split('/')):
        raise ValueError('Ollama URL must not contain encoded or parent path segments')
    return urlunsplit((url.scheme.lower(), url.netloc.lower(), path, '', '')).rstrip('/')


def allowed_bases():
    values = [settings.AI_BASE_URL, *settings.AI_ALLOWED_BASE_URLS]
    local = urlsplit(normalize_base(settings.AI_BASE_URL))
    if local.hostname in {'127.0.0.1', 'localhost'}:
        alias = 'localhost' if local.hostname == '127.0.0.1' else '127.0.0.1'
        values.append(urlunsplit((local.scheme, alias + (f':{local.port}' if local.port else ''), local.path, '', '')))
    return sorted({normalize_base(value) for value in values})


class AIConnection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = True
    base_url: str = Field(max_length=2048)
    model: str = Field(default='', max_length=160)
    embedding_model: str = Field(default_factory=lambda: settings.AI_EMBEDDING_MODEL, max_length=160)
    api_key: SecretStr = Field(default=SecretStr(''), max_length=4096)
    key_header: Literal['Authorization', 'api-key', 'Ocp-Apim-Subscription-Key'] = 'Authorization'
    embeddings_enabled: bool = True
    discovery_enabled: bool = Field(default_factory=lambda: settings.AI_DISCOVERY_ENABLED)
    keep_key: bool = True
    companion_system_prompt: str = Field(default='Answer lifecycle questions from the supplied graph evidence. Explain uncertainty and provider limitations.', min_length=1, max_length=12000)
    agent_configuration: dict[AgentId, AgentConfiguration] = Field(default_factory=dict)
    tool_configuration: dict[ToolId, ToolConfiguration] = Field(default_factory=dict)

    @field_validator('companion_system_prompt')
    @classmethod
    def valid_companion_prompt(cls, value):
        if not value.strip():
            raise ValueError('Companion prompt must not be blank')
        return value

    @field_validator('base_url')
    @classmethod
    def valid_base(cls, value):
        value = normalize_base(value)
        if value not in allowed_bases():
            raise ValueError('Endpoint is not registered in AI_ALLOWED_BASE_URLS; ask the central administrator to add it')
        return value

    @field_validator('model', 'embedding_model')
    @classmethod
    def valid_model(cls, value):
        if any(ord(char) < 33 for char in value) or len(value.encode()) > 320:
            raise ValueError('Use a model identifier without whitespace/control characters')
        return value

    @field_validator('api_key')
    @classmethod
    def valid_key(cls, value):
        if any(ord(char) < 32 or ord(char) == 127 for char in value.get_secret_value()):
            raise ValueError('Invalid API key characters')
        return value

    def private(self):
        return {**self.model_dump(exclude={'api_key', 'keep_key'}), 'api_key': self.api_key.get_secret_value()}

    def public(self):
        return {**self.model_dump(exclude={'api_key', 'keep_key'}), 'key_configured': bool(self.api_key.get_secret_value())}


def connection_for(store, token):
    profile = store.ai_profile(token)
    # OpenAI-compatible central inference remains served by the legacy companion.
    values = profile or {'base_url': settings.AI_BASE_URL, 'enabled': settings.AI_PROVIDER == 'ollama',
                        'model': settings.AI_MODEL, 'embedding_model': settings.AI_EMBEDDING_MODEL,
                        'api_key': server_secret(settings.AI_TOKEN_ENV) or '', 'key_header': settings.AI_KEY_HEADER}
    try:
        return AIConnection.model_validate(values)
    except ValueError:
        # A malformed server-side credential must not appear in exception logs.
        raise HTTPException(422, 'AI connection configuration is invalid; reset the session override or correct central settings.') from None


class OllamaREST:
    def __init__(self, connection, guard=lambda: None, deadline=None):
        self.connection, self.guard = connection, guard
        self.deadline = deadline or time.monotonic() + settings.AI_AGENT_DEADLINE_SECONDS

    def check(self):
        self.guard()
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('AI operation reached its total deadline')
        return remaining

    def request(self, operation, payload=None):
        if operation not in {'tags', 'chat', 'embed'}:
            raise ValueError('Unsupported Ollama operation')
        remaining = self.check()
        if not self.connection.enabled:
            raise ValueError('Enable an AI connection first')
        if payload is not None and len(json.dumps(payload).encode()) > settings.AI_CONTEXT_MAX_BYTES:
            raise ValueError('AI request exceeded the configured context byte budget')
        headers = {}
        key = self.connection.api_key.get_secret_value()
        if key:
            headers[self.connection.key_header] = ('Bearer ' + key) if self.connection.key_header == 'Authorization' else key
        # Only pre-registered bases; no redirects, proxy inheritance or URLs in errors.
        with httpx.Client(timeout=min(settings.AI_TIMEOUT_SECONDS, remaining), follow_redirects=False, trust_env=False) as client:
            with client.stream('GET' if payload is None else 'POST', self.connection.base_url + '/api/' + operation,
                               headers=headers, **({'json': payload} if payload is not None else {})) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    self.check()
                    if len(content) + len(chunk) > settings.AI_MAX_RESPONSE_BYTES:
                        raise ValueError('AI response exceeded the configured byte budget')
                    content.extend(chunk)
        self.check()
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError('Expected an Ollama JSON object')
        return result

    def models(self):
        response = self.request('tags')
        if not isinstance(response, dict):
            raise ValueError('Invalid model discovery response')
        items = response.get('models', [])
        if not isinstance(items, list):
            raise ValueError('Invalid model discovery response')
        return sorted({item['name'] for item in items[:1000] if isinstance(item, dict) and isinstance(item.get('name'), str) and len(item['name']) <= 160})

    def embed(self, texts):
        if not self.connection.embedding_model:
            raise ValueError('Select an embedding model')
        response = self.request('embed', {'model': self.connection.embedding_model, 'input': texts, 'truncate': False})
        if not isinstance(response, dict):
            raise ValueError('Invalid embedding response')
        vectors = response.get('embeddings')
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ValueError('Embedding count does not match input')
        dimension = None
        for vector in vectors:
            if not isinstance(vector, list) or not 1 <= len(vector) <= 8192:
                raise ValueError('Invalid embedding dimension')
            if dimension is not None and len(vector) != dimension:
                raise ValueError('Inconsistent embedding dimensions')
            dimension = len(vector)
            try:
                if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector):
                    raise ValueError('Embedding contains invalid values')
                norm = math.sqrt(sum(float(value) * float(value) for value in vector))
            except OverflowError:
                raise ValueError('Embedding contains values outside the supported numeric range') from None
            if not math.isfinite(norm) or not norm:
                raise ValueError('Embedding has zero or invalid magnitude')
        return vectors

    def chat(self, messages, tools=None):
        if not self.connection.model:
            raise ValueError('Select a chat model')
        payload = {'model': self.connection.model, 'messages': messages, 'stream': False,
                   'options': {'temperature': 0.1, 'num_predict': settings.AI_MAX_OUTPUT_TOKENS}}
        if tools:
            payload['tools'] = tools
        else:
            payload['format'] = 'json'
        result = self.request('chat', payload)
        if not isinstance(result, dict):
            raise ValueError('Invalid chat response')
        message = result.get('message')
        if not isinstance(message, dict) or message.get('role', 'assistant') != 'assistant':
            raise ValueError('Invalid chat response')
        return message
