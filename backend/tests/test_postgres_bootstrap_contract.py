"""Dependency-free driver contract checks; no PostgreSQL server is contacted."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import AsyncMock, patch


class BootstrapContract(unittest.TestCase):
    def load(self, driver):
        config = ModuleType('core.config')
        config.settings = SimpleNamespace(POSTGRES_HOST='localhost', POSTGRES_PORT=5432,
            POSTGRES_USER='service', POSTGRES_PASSWORD='secret:@/', POSTGRES_DB='trace_test',
            POSTGRES_CONNECT_TIMEOUT_SECONDS=10)
        spec = importlib.util.spec_from_file_location('bootstrap_contract', Path(__file__).parents[1] / 'database/init_db.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'core.config': config, 'asyncpg': driver}):
            spec.loader.exec_module(module)
        return module

    def driver(self, exists=False):
        conn = SimpleNamespace(fetchval=AsyncMock(return_value=exists), execute=AsyncMock(), close=AsyncMock())
        driver = ModuleType('asyncpg')
        driver.connect = AsyncMock(return_value=conn)
        driver.DuplicateDatabaseError = type('DuplicateDatabaseError', (Exception,), {})
        return driver, conn

    def test_create_uses_keywords_and_closes_connection(self):
        driver, conn = self.driver()
        module = self.load(driver)
        with patch.dict(sys.modules, {'asyncpg': driver}):
            asyncio.run(module.create_database_if_not_exists())
        self.assertEqual(driver.connect.call_args.kwargs['password'], 'secret:@/')
        conn.execute.assert_awaited_once_with('CREATE DATABASE "trace_test"')
        conn.close.assert_awaited_once()

    def test_existing_database_is_not_recreated(self):
        driver, conn = self.driver(exists=True)
        module = self.load(driver)
        with patch.dict(sys.modules, {'asyncpg': driver}):
            asyncio.run(module.create_database_if_not_exists())
        conn.execute.assert_not_awaited()
        conn.close.assert_awaited_once()

    def test_connection_closes_on_creation_failure(self):
        driver, conn = self.driver()
        conn.execute.side_effect = RuntimeError('failure')
        module = self.load(driver)
        with patch.dict(sys.modules, {'asyncpg': driver}), self.assertRaises(RuntimeError):
            asyncio.run(module.create_database_if_not_exists())
        conn.close.assert_awaited_once()

    def test_missing_password_fails_before_connecting(self):
        driver, conn = self.driver()
        module = self.load(driver)
        module.settings.POSTGRES_PASSWORD = ''
        with patch.dict(sys.modules, {'asyncpg': driver}), self.assertRaises(ValueError):
            asyncio.run(module.create_database_if_not_exists())
        driver.connect.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
