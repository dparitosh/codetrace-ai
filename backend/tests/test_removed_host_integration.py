"""Keep removed host integrations and hosted workflows out of this application."""
import pytest
import re
from core.config import PROJECT_ROOT
from core.connection_models import PipelineProvider


def test_removed_pipeline_platform_is_rejected():
    with pytest.raises(ValueError):
        PipelineProvider(id='removed', label='Removed provider', platform='github',
                         repository_id='workspace', endpoint='https://example.org/pipelines')
    provider = PipelineProvider(id='ci', label='GitLab CI', platform='gitlab',
                                repository_id='workspace', endpoint='https://gitlab.example.org/pipelines')
    assert provider.platform == 'gitlab'


def test_hosted_workflows_and_obsolete_remote_cli_are_absent():
    assert not [path for path in (PROJECT_ROOT / '.github').rglob('*') if path.is_file()]
    assert not (PROJECT_ROOT / 'cli/codetrace.js').exists()
    assert not (PROJECT_ROOT / 'cli/package.json').exists()


def test_removed_host_names_and_response_contracts_are_absent_from_runtime_sources():
    paths = []
    for directory in ('backend', 'frontend/src', 'codegraph_core/codegraph_core', 'scripts', 'config'):
        paths.extend(path for path in (PROJECT_ROOT / directory).rglob('*')
                     if path.is_file() and path.suffix in {'.py', '.js', '.ts', '.tsx', '.mjs', '.json'}
                     and 'tests' not in path.parts and '__pycache__' not in path.parts
                     and '.test.' not in path.name)
    paths.extend([PROJECT_ROOT / '.env.local.example', PROJECT_ROOT / 'frontend/package.json',
                  PROJECT_ROOT / 'codegraph_core/pyproject.toml',
                  PROJECT_ROOT / 'backend/requirements-local.txt', PROJECT_ROOT / 'backend/requirements.txt'])
    for extension in ('*.ps1', '*.sh', '*.bat'):
        paths.extend(PROJECT_ROOT.glob(extension))
    forbidden = re.compile(r'github|workflow_runs|head_sha|head_branch', re.IGNORECASE)
    matches = [str(path.relative_to(PROJECT_ROOT)) for path in paths
               if forbidden.search(path.read_text(encoding='utf-8-sig'))]
    assert not matches, matches


def test_removed_runtime_api_paths_are_absent():
    from main import app
    paths = app.openapi()['paths']
    assert not [path for path in paths if 'github' in path.lower() or '/mcp' in path.lower()]
    assert '/api/v1/graph/local' in paths and '/api/v1/graph/gitlab' in paths
