"""Tests for shared/db.py."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import db


class TestDbPoolInit:
    """Test pool initialization and teardown."""

    async def test_init_pool_no_dsn(self):
        """Test that init_pool raises ValueError without DSN."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DATABASE_URL"):
                await db.init_pool()

    async def test_init_pool_explicit_dsn(self):
        """Test that init_pool accepts an explicit DSN."""
        mock_pool = AsyncMock()
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool
            await db.init_pool(dsn="postgresql://user:pass@localhost/test")
            mock_create.assert_called_once()
            # Should have been called with our DSN
            args, kwargs = mock_create.call_args
            assert kwargs["dsn"] == "postgresql://user:pass@localhost/test"
            assert kwargs["min_size"] == 2
            assert kwargs["max_size"] == 10
        # Clean up - close the pool
        if db._pool is not None:
            await db.close_pool()

    async def test_init_pool_from_env(self):
        """Test that init_pool reads DATABASE_URL from env."""
        mock_pool = AsyncMock()
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://env:pass@localhost/test"}):
            with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = mock_pool
                await db.init_pool()
                args, kwargs = mock_create.call_args
                assert kwargs["dsn"] == "postgresql://env:pass@localhost/test"
        if db._pool is not None:
            await db.close_pool()

    async def test_reinitialize_pool(self):
        """Test that re-initializing closes the old pool."""
        old_pool = AsyncMock()
        new_pool = AsyncMock()
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [old_pool, new_pool]
            await db.init_pool(dsn="postgresql://user:pass@localhost/first")
            await db.init_pool(dsn="postgresql://user:pass@localhost/second")
            old_pool.close.assert_awaited_once()
        if db._pool is not None:
            await db.close_pool()

    async def test_get_pool_not_initialized(self):
        """Test that get_pool raises RuntimeError before init."""
        db._pool = None
        with pytest.raises(RuntimeError, match="not initialized"):
            await db.get_pool()

    async def test_close_pool_not_initialized(self):
        """Test that close_pool handles None gracefully."""
        db._pool = None
        # Should not raise
        await db.close_pool()

    async def test_full_lifecycle(self):
        """Test the full init → query → close lifecycle."""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"id": 1}]
        # acquire() is not a coroutine - it returns an async context manager directly
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None

        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_pool

            # Init
            await db.init_pool(dsn="postgresql://user:pass@localhost/test")
            assert db._pool is not None

            # Query
            result = await db.fetch("SELECT 1")
            assert result == [{"id": 1}]
            mock_conn.fetch.assert_awaited_once_with("SELECT 1")

            # Close
            await db.close_pool()
            assert db._pool is None
            mock_pool.close.assert_awaited_once()


class TestDbQueryHelpers:
    """Test the query helper functions."""

    @pytest.fixture(autouse=True)
    async def setup_pool(self):
        """Set up a mock pool for each test."""
        self.mock_pool = AsyncMock()
        self.mock_conn = AsyncMock()
        # acquire() is not a coroutine - it returns an async context manager directly
        self.mock_pool.acquire = MagicMock()
        self.mock_pool.acquire.return_value.__aenter__.return_value = self.mock_conn
        self.mock_pool.acquire.return_value.__aexit__.return_value = None

        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = self.mock_pool
            await db.init_pool(dsn="postgresql://user:pass@localhost/test")
        yield
        if db._pool is not None:
            await db.close_pool()
        db._pool = None

    async def test_fetch(self):
        """Test fetch returns all rows."""
        self.mock_conn.fetch.return_value = [{"id": 1}, {"id": 2}]
        result = await db.fetch("SELECT * FROM test")
        assert len(result) == 2
        self.mock_conn.fetch.assert_awaited_once_with("SELECT * FROM test")

    async def test_fetch_one(self):
        """Test fetch_one returns a single row."""
        self.mock_conn.fetchrow.return_value = {"id": 1}
        result = await db.fetch_one("SELECT * FROM test WHERE id = $1", 1)
        assert result["id"] == 1
        self.mock_conn.fetchrow.assert_awaited_once_with("SELECT * FROM test WHERE id = $1", 1)

    async def test_fetch_one_none(self):
        """Test fetch_one returns None when no rows."""
        self.mock_conn.fetchrow.return_value = None
        result = await db.fetch_one("SELECT * FROM test WHERE id = $1", 999)
        assert result is None

    async def test_fetch_val(self):
        """Test fetch_val returns a single value."""
        self.mock_conn.fetchval.return_value = 42
        result = await db.fetch_val("SELECT count(*) FROM test")
        assert result == 42
        self.mock_conn.fetchval.assert_awaited_once_with("SELECT count(*) FROM test")

    async def test_execute(self):
        """Test execute returns status string."""
        self.mock_conn.execute.return_value = "INSERT 0 1"
        result = await db.execute("INSERT INTO test VALUES ($1)", "hello")
        assert result == "INSERT 0 1"
        self.mock_conn.execute.assert_awaited_once_with("INSERT INTO test VALUES ($1)", "hello")

    async def test_execute_many(self):
        """Test execute_many with multiple parameter sets."""
        args_list = [("a",), ("b",), ("c",)]
        await db.execute_many("INSERT INTO test VALUES ($1)", args_list)
        self.mock_conn.executemany.assert_awaited_once_with("INSERT INTO test VALUES ($1)", args_list)

    async def test_fetch_with_args(self):
        """Test fetch with parameters."""
        self.mock_conn.fetch.return_value = [{"name": "test"}]
        await db.fetch("SELECT * FROM test WHERE name = $1", "test")
        self.mock_conn.fetch.assert_awaited_once_with(
            "SELECT * FROM test WHERE name = $1", "test"
        )


class TestDbTransaction:
    """Test the transaction context manager."""

    @pytest.fixture(autouse=True)
    async def setup_pool(self):
        """Set up a mock pool."""
        self.mock_pool = AsyncMock()
        self.mock_conn = AsyncMock()
        # acquire() is not a coroutine - it returns an async context manager directly
        self.mock_pool.acquire = MagicMock()
        self.mock_pool.acquire.return_value.__aenter__.return_value = self.mock_conn
        self.mock_pool.acquire.return_value.__aexit__.return_value = None
        # conn.transaction() is also an async context manager (not a coroutine)
        self.mock_conn.transaction = MagicMock()
        self.mock_conn.transaction.return_value.__aenter__.return_value = None
        self.mock_conn.transaction.return_value.__aexit__.return_value = None

        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = self.mock_pool
            await db.init_pool(dsn="postgresql://user:pass@localhost/test")
        yield
        if db._pool is not None:
            await db.close_pool()
        db._pool = None

    async def test_transaction_commit(self):
        """Test that transaction commits on success."""
        async with db.transaction() as conn:
            await conn.execute("INSERT INTO test VALUES (1)")
        # The inner connection should have been used
        self.mock_conn.execute.assert_awaited_once_with("INSERT INTO test VALUES (1)")

    async def test_transaction_rollback(self):
        """Test that transaction rolls back on exception."""
        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO test VALUES (1)")
                raise TestError("force rollback")