"""Compatibility entry point for centrally configured PostgreSQL bootstrap."""
from database.init_db import main

if __name__ == '__main__':
    raise SystemExit(main())
