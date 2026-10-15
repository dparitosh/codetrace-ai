"""Git commands that never inherit executable host Git configuration."""
import base64
import os
from pathlib import Path


def git_environment(home, token=None):
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    # Do not inherit GIT_CONFIG_*, askpass programs, alternate object directories,
    # SSH commands, proxy commands, or user/system credential helpers.
    allowed = {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATHEXT'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home),
               GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM='1',
               GIT_TEMPLATE_DIR=str(home), GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    if token:
        # A configured access token is passed via the child environment, never
        # embedded in a URL, command line, clone config, or returned error.
        auth = base64.b64encode(('oauth2:' + token).encode()).decode()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.extraHeader',
                   GIT_CONFIG_VALUE_0='Authorization: Basic ' + auth)
    return env


def git_command():
    return ['git', '-c', 'http.followRedirects=false', '-c', 'core.hooksPath=',
            '-c', 'core.fsmonitor=false', '-c', 'credential.helper=',
            '-c', 'protocol.allow=never', '-c', 'protocol.https.allow=always',
            '-c', 'protocol.http.allow=always', '-c', 'submodule.recurse=false']
