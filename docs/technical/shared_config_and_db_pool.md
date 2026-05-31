# Shared Config Loader & DB Connection Pool

## 1. Feature Overview
**Purpose**: Provide shared infrastructure for YAML config loading and async PostgreSQL connection pooling
**Business Value**: Centralized configuration and database access used by all modules, avoiding duplication
**Scope**: `shared/config_loader.py` (YAML loading + env var substitution), `shared/db.py` (asyncpg pool + query helpers)
**Success Criteria**: All YAML configs loadable with env var substitution; DB pool initializes, executes queries, and closes cleanly

## 2. Service Ownership
**Primary Service**: `shared/`
**Dependent Services**: All modules depend on both config_loader and db
**Interface Changes**: New shared utilities (no external API changes)

## 3. Detailed Implementation

### Config Loader (`shared/config_loader.py`)

**Responsibilities**:
1. Load YAML files from `config/` directory
2. Substitute `${ENV_VAR}` patterns with environment variable values
3. Cache loaded configs in memory (reload on file change not required for MVP)
4. Provide typed access to config sections

**Interface**:
```python
# shared/config_loader.py
import yaml
import os
import re
from pathlib import Path
from typing import Any

_CONFIG_CACHE: dict[str, dict] = {}
_CONFIG_DIR = Path(__file__).parent.parent / "config"

def _substitute_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} patterns with environment variable values.
    If env var not found, leave the pattern as-is (no error)."""

def load_config(name: str) -> dict[str, Any]:
    """Load a YAML config file by name (without .yaml extension).
    Example: load_config("platforms") loads config/platforms.yaml
    Substitutes ${ENV_VAR} patterns in all string values.
    Caches result in memory."""

def get_content_template() -> dict[str, Any]:
    """Shortcut for load_config("content_template")"""

def get_platforms_config() -> dict[str, Any]:
    """Shortcut for load_config("platforms")"""

def get_backup_trends() -> dict[str, Any]:
    """Shortcut for load_config("backup_trends")"""
```

**Env Var Substitution Rules**:
- Pattern: `${VAR_NAME}` anywhere in a string value
- Recursion: Substitutes in nested dicts and lists
- Missing var: Leave `${VAR_NAME}` as-is, log WARNING
- Non-string values: No substitution (int, bool, etc.)

### DB Connection Pool (`shared/db.py`)

**Responsibilities**:
1. Create and manage an `asyncpg` connection pool
2. Provide helper methods for common query patterns
3. Initialize pool on app startup, close on shutdown
4. Use `DATABASE_URL` from environment

**Interface**:
```python
# shared/db.py
import asyncpg
from typing import Any

_pool: asyncpg.Pool | None = None

async def init_pool(dsn: str | None = None, min_size: int = 2, max_size: int = 10) -> None:
    """Initialize the connection pool. Uses DATABASE_URL env var if dsn not provided."""

async def close_pool() -> None:
    """Close the connection pool gracefully."""

async def get_pool() -> asyncpg.Pool:
    """Get the active connection pool. Raises RuntimeError if not initialized."""

async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Execute a SELECT query and return all rows."""

async def fetch_one(query: str, *args: Any) -> asyncpg.Record | None:
    """Execute a SELECT query and return a single row or None."""

async def fetch_val(query: str, *args: Any) -> Any:
    """Execute a query and return a single value (first column of first row)."""

async def execute(query: str, *args: Any) -> str:
    """Execute an INSERT/UPDATE/DELETE query. Returns status string."""

async def execute_many(query: str, args_list: list[tuple]) -> None:
    """Execute a query with multiple parameter sets (batch insert)."""

async def transaction():
    """Context manager for database transactions.
    Usage: async with db.transaction() as conn: ..."""
```

**Pool Configuration**:
- Default min_size: 2 connections
- Default max_size: 10 connections
- Connection timeout: 30 seconds
- Command timeout: 60 seconds
- Statement cache: disabled (for compatibility with pgbouncer if used later)

## 4. Error Handling
**Expected Failures**:
- YAML file not found
- YAML syntax error
- Database connection refused
- Query execution error
- Pool not initialized when queried

**Recovery Strategies**:
- Missing YAML: Raise `FileNotFoundError` with clear message including expected path
- YAML syntax: Raise `yaml.YAMLError` with file name and line number
- Connection refused: Raise `asyncpg.CannotConnectNow` with DSN (password masked)
- Query error: Raise `asyncpg.PostgresError` with query context
- Pool not initialized: Raise `RuntimeError("Database pool not initialized. Call init_pool() first.")`

**Logging Requirements**:
- INFO: Config loaded successfully, pool initialized with N connections
- WARNING: Env var not found during substitution
- ERROR: Connection failure, query failure

## 5. Input/Output Specifications
**Input Validation**:
- Config name: must be a valid filename (alphanumeric + underscore)
- DSN: validated by asyncpg on connection
- Query args: validated by asyncpg parameter binding

**Output Formats**:
- `fetch()`: Returns `list[asyncpg.Record]` (dict-like access)
- `fetch_one()`: Returns `asyncpg.Record | None`
- `fetch_val()`: Returns raw Python type (int, str, etc.)
- Config: Returns nested `dict[str, Any]`

## 6. Edge Cases
- Empty YAML file (returns empty dict)
- YAML with only comments (returns None → treat as empty dict)
- Environment variable references another variable (`${A}_${B}`)
- Circular env var references (detect and raise)
- Database URL with special characters in password
- Pool exhaustion (all connections busy)

## 7. Dependencies
- `pyyaml` for YAML parsing
- `asyncpg` for PostgreSQL async driver
- `DATABASE_URL` environment variable

## 8. Testing Requirements
- **Unit tests**: Env var substitution (simple, nested, missing vars), YAML loading
- **Integration tests**: Pool init/query/close lifecycle with test database
- **Error tests**: Missing file, bad YAML, connection failure
- **Concurrency test**: Parallel queries through the pool

## 9. Deployment Considerations
- **Migration**: None (new files only)
- **Rollback**: N/A
- **Monitoring**: Log pool stats (active/idle connections) periodically
- **Performance**: Pool size should match expected concurrency (10 for MVP)
