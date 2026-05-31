"""Async PostgreSQL connection pool with high-level query helpers."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(
    dsn: str | None = None,
    min_size: int = 2,
    max_size: int = 10,
    command_timeout: int = 60,
    connection_timeout: int = 30,
) -> None:
    """Initialize the connection pool.

    Args:
        dsn: PostgreSQL connection string. Falls back to DATABASE_URL env var.
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.
        command_timeout: Maximum time (seconds) to wait for a query result.
        connection_timeout: Maximum time (seconds) to wait for a connection.

    Raises:
        asyncpg.CannotConnectNow: If the database cannot be reached.
    """
    global _pool
    if _pool is not None:
        logger.warning("Pool already initialized; closing existing pool first.")
        await close_pool()

    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise ValueError(
            "No DSN provided and DATABASE_URL environment variable is not set."
        )

    logger.info("Initializing connection pool (min=%d, max=%d)...", min_size, max_size)
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        timeout=connection_timeout,
        # Disable statement cache for pgbouncer compatibility
        statement_cache_size=0,
    )
    logger.info(
        "Connection pool initialized with %d connections.", min_size if min_size > 0 else 2
    )


async def close_pool() -> None:
    """Close the connection pool gracefully."""
    global _pool
    if _pool is None:
        logger.warning("close_pool() called but pool was not initialized.")
        return
    logger.info("Closing connection pool...")
    await _pool.close()
    _pool = None
    logger.info("Connection pool closed.")


async def get_pool() -> asyncpg.Pool:
    """Get the active connection pool.

    Raises:
        RuntimeError: If the pool has not been initialized.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. Call init_pool() first."
        )
    return _pool


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Execute a SELECT query and return all rows.

    Returns:
        List of asyncpg.Record objects (dict-like access).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetch_one(query: str, *args: Any) -> asyncpg.Record | None:
    """Execute a SELECT query and return a single row or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch_val(query: str, *args: Any) -> Any:
    """Execute a query and return the first column of the first row.

    Returns:
        A single Python value (int, str, etc.) or None.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    """Execute an INSERT/UPDATE/DELETE query.

    Returns:
        Status string (e.g. "INSERT 0 1").
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def execute_many(query: str, args_list: list[tuple]) -> None:
    """Execute a query with multiple parameter sets (batch insert/update)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(query, args_list)


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    """Context manager for database transactions.

    Usage:
        async with db.transaction() as conn:
            await conn.execute("INSERT INTO ...")
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn