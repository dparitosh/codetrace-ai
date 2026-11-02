"""Offline launcher regressions using disposable copies, never real installers."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from core.config import PROJECT_ROOT

SHELL = shutil.which('pwsh') or shutil.which('powershell')
WINDOWS = pytest.mark.skipif(os.name != 'nt' or not SHELL, reason='Windows PowerShell launcher fixture')


def invoke(script, env):
    command = r"""
function Get-Command {
    param([string]$Name, [object]$ErrorAction)
    if ($Name -eq 'npm.cmd') { return [pscustomobject]@{Source='unused-npm.cmd'} }
    if ($Name -eq 'node' -and $env:LAUNCH_FAKE_NODE) { return [pscustomobject]@{Source=$env:LAUNCH_FAKE_NODE} }
    Microsoft.PowerShell.Core\Get-Command -Name $Name -ErrorAction Stop
}
if ($env:LAUNCH_FAKE_PYTHON) { & $env:LAUNCH_SCRIPT -PythonPath $env:LAUNCH_FAKE_PYTHON }
else { & $env:LAUNCH_SCRIPT }
"""
    return subprocess.run([SHELL, '-NoProfile', '-NonInteractive', '-Command', command],
                          env={**os.environ, **env, 'LAUNCH_SCRIPT': str(script)},
                          capture_output=True, text=True, timeout=20)


@WINDOWS
def test_install_rejects_old_python_before_creating_environment(tmp_path):
    root = tmp_path / 'installation fixture'; root.mkdir()
    script = root / 'install.ps1'; shutil.copyfile(PROJECT_ROOT / 'install.ps1', script)
    fake = root / 'old-python.cmd'; fake.write_text('@echo off\nexit /b 1\n', encoding='utf-8')
    result = invoke(script, {'LAUNCH_FAKE_PYTHON': str(fake), 'LAUNCH_FAKE_NODE': ''})
    assert result.returncode != 0
    assert 'Python 3.10+ is required' in result.stderr
    assert not (root / '.env.local').exists() and not (root / '.venv').exists()


@WINDOWS
@pytest.mark.parametrize('exit_code', [0, 5])
def test_foreground_frontend_uses_node_directly_and_reports_exit(tmp_path, exit_code):
    root = tmp_path / 'frontend fixture'; root.mkdir()
    script = root / 'start-frontend.ps1'; shutil.copyfile(PROJECT_ROOT / 'start-frontend.ps1', script)
    vite = root / 'frontend/node_modules/vite/bin/vite.js'; vite.parent.mkdir(parents=True); vite.write_text('// fixture', encoding='utf-8')
    marker = root / 'launched.txt'
    fake = root / 'node-fixture.cmd'
    fake.write_text('@echo off\n> "%LAUNCH_MARKER%" echo %~1\nexit /b '+str(exit_code)+'\n', encoding='utf-8')
    result = invoke(script, {'LAUNCH_FAKE_PYTHON':'', 'LAUNCH_FAKE_NODE':str(fake), 'LAUNCH_MARKER':str(marker)})
    assert marker.read_text(encoding='utf-8').strip() == str(vite)
    assert (result.returncode == 0) == (exit_code == 0)
    if exit_code:
        assert 'Frontend exited with code 5' in result.stderr


def test_shell_entrypoints_have_lf_endings_in_windows_checkouts():
    for name in ('install.sh', 'start.sh'):
        content = (PROJECT_ROOT / name).read_bytes()
        assert content.startswith(b'#!/usr/bin/env bash\n') and b'\r' not in content
    assert '*.sh text eol=lf' in (PROJECT_ROOT / '.gitattributes').read_text(encoding='utf-8')
