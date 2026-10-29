"""Keep removed host integrations and hosted workflows out of this application."""
import pytest
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
    workflows = PROJECT_ROOT / '.github/workflows'
    assert not list(workflows.glob('*.yml'))
    assert not list(workflows.glob('*.yaml'))
    assert not (PROJECT_ROOT / 'cli/codetrace.js').exists()
    assert not (PROJECT_ROOT / 'cli/package.json').exists()
