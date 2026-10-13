"""Print only the public settings needed by native launchers."""
import json
from core.config import settings

if __name__ == '__main__':
    print(json.dumps({
        'frontend': settings.frontend_url,
        'backend': f'http://{settings.browser_host}:{settings.PORT}',
        'logs': str(settings.LOG_DIR),
        'ports': [settings.PORT, settings.FRONTEND_PORT],
        'startupTimeout': settings.STARTUP_TIMEOUT_SECONDS,
    }))
