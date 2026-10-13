"""Compatibility entry point; configuration comes from root .env.local."""
from database.init_db import main

if __name__ == '__main__':
    raise SystemExit(main())
