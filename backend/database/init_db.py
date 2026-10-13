"""Explicit PostgreSQL bootstrap; creates missing tables, never seeds data.

This is not a versioned migration and does not alter existing table columns.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import settings


async def create_database_if_not_exists():
    import asyncpg
    if not settings.POSTGRES_PASSWORD:
        raise ValueError('Set POSTGRES_PASSWORD in central configuration before PostgreSQL setup')
    conn = await asyncpg.connect(host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD, database='postgres',
        timeout=settings.POSTGRES_CONNECT_TIMEOUT_SECONDS)
    try:
        exists = await conn.fetchval('SELECT 1 FROM pg_database WHERE datname = $1', settings.POSTGRES_DB)
        if not exists:
            try:
                await conn.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
            except asyncpg.DuplicateDatabaseError:
                pass
    finally:
        await conn.close()


def create_tables():
    from database.connection import engine, Base
    from database import models, enhanced_models
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)


async def init_database():
    await create_database_if_not_exists()
    await asyncio.to_thread(create_tables)
    print('PostgreSQL bootstrap completed. No sample data inserted; existing columns unchanged.')


def main():
    try:
        asyncio.run(init_database())
    except Exception as exc:
        print(f'PostgreSQL bootstrap failed ({type(exc).__name__}). Check configuration and server permissions.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
