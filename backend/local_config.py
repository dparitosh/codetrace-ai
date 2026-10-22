"""Print only the public settings needed by native launchers."""
import json
import sys
from pydantic import ValidationError
from pydantic_settings import SettingsError

def main():
    try:
        from core.config import settings
    except ValidationError as error:
        print('Invalid configuration. Check .env.local and process environment:', file=sys.stderr)
        for issue in error.errors(include_input=False, include_context=False, include_url=False):
            field = '.'.join(map(str, issue['loc'])) or 'Settings'
            print(f"  {field}: {issue['msg']}", file=sys.stderr)
        return 2
    except SettingsError as error:
        # SettingsError identifies the field/source, without dumping raw values
        # or the underlying JSON decoder traceback.
        print(f'Invalid configuration: {error}. Check .env.local and process environment.', file=sys.stderr)
        return 2
    print(json.dumps({
        'frontend': settings.frontend_url,
        'backend': f'http://{settings.browser_host}:{settings.PORT}',
        'logs': str(settings.LOG_DIR),
        'ports': [settings.PORT, settings.FRONTEND_PORT],
        'startupTimeout': settings.STARTUP_TIMEOUT_SECONDS,
    }))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
