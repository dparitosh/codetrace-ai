"""Conservative raw-byte Git revision checks without worktree filter execution."""
import hashlib
import subprocess
from pathlib import Path

from core.config import settings
from services.git_isolation import git_command


def raw_revision(root, env):
    root = Path(root).resolve()

    def git(*args):
        result = subprocess.run(git_command() + ['-C', str(root), *args], capture_output=True,
                                timeout=5, check=False, env=env)
        if result.returncode or len(result.stdout) > settings.MAX_LOCAL_PAYLOAD_BYTES:
            raise ValueError('Git metadata is unavailable or over budget')
        return result.stdout

    try:
        revision = git('rev-parse', 'HEAD').decode('ascii').strip()
        algorithm = git('rev-parse', '--show-object-format').decode('ascii').strip()
        if algorithm not in {'sha1', 'sha256'}:
            return None
        entries = git('ls-tree', '-r', '-z', '--full-tree', revision).split(b'\0')
        tracked, total = set(), 0
        for entry in entries:
            if not entry:
                continue
            metadata, name = entry.split(b'\t', 1)
            mode, kind, expected = metadata.split()
            if kind != b'blob' or mode not in {b'100644', b'100755'}:
                return None  # No assumptions about submodules or symlink targets.
            relative = name.decode('utf-8')
            file = root / relative
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                return None
            with file.open('rb') as stream:
                data = stream.read(settings.MAX_LOCAL_PAYLOAD_BYTES + 1)
            total += len(data)
            if total > settings.MAX_LOCAL_PAYLOAD_BYTES:
                return None
            blob = b'blob ' + str(len(data)).encode() + b'\0' + data
            if hashlib.new(algorithm, blob).hexdigest().encode() != expected:
                return None
            tracked.add(name)
        # ls-files lists names only; it does not run clean/process filters.
        names = {name for name in git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split(b'\0') if name}
        if names != tracked or git('rev-parse', 'HEAD').decode('ascii').strip() != revision:
            return None
        return revision
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
        return None
