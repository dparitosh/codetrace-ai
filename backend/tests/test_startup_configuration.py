"""Offline startup diagnostics must name bad settings without exposing values."""
import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from core.config import PROJECT_ROOT, Settings


@pytest.mark.parametrize('values,field', [
    ({'AI_BASE_URL': '127.0.0.1:11434'}, 'AI_BASE_URL'),
    ({'AI_BASE_URL': 'https://user:startup-secret-sentinel@example.org'}, 'AI_BASE_URL'),
    ({'AI_ALLOWED_BASE_URLS': ['http://127.0.0.1:11434', 'not-a-url']}, 'AI_ALLOWED_BASE_URLS'),
    ({'OSLC_PUBLIC_BASE_URL': 'not-a-url'}, 'OSLC_PUBLIC_BASE_URL'),
    ({'HOST': 'http://127.0.0.1'}, 'HOST'),
    ({'HOST': 'localhost:8009'}, 'HOST'),
])
def test_configuration_error_names_field_and_hides_input(values, field):
    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None, AI_PROVIDER='disabled', **values)
    assert failure.value.errors()[0]['loc'][0] == field
    assert 'input_value' not in str(failure.value)
    assert 'startup-secret-sentinel' not in str(failure.value)


@pytest.mark.parametrize('host,expected', [
    ('localhost', 'localhost'), ('127.0.0.1', '127.0.0.1'),
    ('::', '127.0.0.1'), ('::1', '[::1]'), ('[::1]', '[::1]'),
])
def test_valid_bind_hosts_generate_valid_launcher_urls(host, expected):
    settings = Settings(_env_file=None, AI_PROVIDER='disabled', HOST=host)
    assert settings.frontend_url == f'http://{expected}:{settings.FRONTEND_PORT}'
    assert settings.OSLC_PUBLIC_BASE_URL == f'http://{expected}:{settings.PORT}/oslc'


def run_launcher_config(**values):
    return subprocess.run([sys.executable, str(PROJECT_ROOT / 'backend/local_config.py')],
                          cwd=PROJECT_ROOT, env={**os.environ, **values},
                          capture_output=True, text=True, timeout=20)


def test_launcher_diagnostic_hides_credentials_and_full_settings():
    result = run_launcher_config(AI_BASE_URL='https://user:startup-secret-sentinel@example.org',
                                 POSTGRES_PASSWORD='postgres-secret-sentinel')
    assert result.returncode == 2
    assert 'AI_BASE_URL:' in result.stderr
    assert not result.stdout
    assert 'Traceback' not in result.stderr
    assert 'startup-secret-sentinel' not in result.stderr
    assert 'postgres-secret-sentinel' not in result.stderr


def test_launcher_diagnostic_reports_malformed_json_field():
    result = run_launcher_config(AI_ALLOWED_BASE_URLS='[startup-secret-sentinel')
    assert result.returncode == 2
    assert 'AI_ALLOWED_BASE_URLS' in result.stderr
    assert 'Traceback' not in result.stderr
    assert 'startup-secret-sentinel' not in result.stderr


def test_valid_launcher_configuration_preserves_public_json_contract():
    result = run_launcher_config(AI_PROVIDER='disabled', AI_BASE_URL='http://127.0.0.1:11434',
                                 AI_ALLOWED_BASE_URLS='[]', HOST='127.0.0.1', OSLC_PUBLIC_BASE_URL='')
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert set(data) == {'frontend', 'backend', 'logs', 'ports', 'startupTimeout'}
    assert data['backend'].startswith('http://127.0.0.1:')
    assert not result.stderr


@pytest.mark.parametrize('endpoint', ['http://127.0.0.1:1434', 'http://models.example/ollama', 'https://models.example/ollama'])
def test_ai_allows_http_by_default_without_rewriting_scheme(endpoint):
    configured = Settings(_env_file=None, AI_PROVIDER='ollama', AI_MODEL='installed',
                          AI_BASE_URL=endpoint, AI_ALLOWED_BASE_URLS=[])
    assert configured.AI_REQUIRE_HTTPS is False and configured.AI_BASE_URL == endpoint


@pytest.mark.parametrize('endpoint', ['http://127.0.0.1:1434', 'http://models.example/ollama'])
def test_ai_https_policy_is_explicit_and_names_configuration(endpoint):
    with pytest.raises(ValidationError, match='AI_REQUIRE_HTTPS=true'):
        Settings(_env_file=None, AI_REQUIRE_HTTPS=True, AI_BASE_URL=endpoint, AI_ALLOWED_BASE_URLS=[])
    configured = Settings(_env_file=None, AI_REQUIRE_HTTPS=True, AI_BASE_URL='https://models.example/ollama', AI_ALLOWED_BASE_URLS=[])
    assert configured.AI_BASE_URL.startswith('https://')


def test_https_policy_checks_additional_ai_bases_without_affecting_other_integrations():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, AI_REQUIRE_HTTPS=True, AI_BASE_URL='https://models.example',
                 AI_ALLOWED_BASE_URLS=['http://other.example'])
    assert error.value.errors()[0]['loc'][0] == 'AI_ALLOWED_BASE_URLS'
    with pytest.raises(ValidationError, match='Remote endpoints must use HTTPS'):
        Settings(_env_file=None, AI_REQUIRE_HTTPS=False, OSLC_PUBLIC_BASE_URL='http://alm.example')
