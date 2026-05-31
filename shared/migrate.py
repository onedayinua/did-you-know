import asyncio
import asyncpg
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone


class MigrationError(Exception):
    """Raised when a migration fails to apply."""
    def __init__(self, version: int, name: str, original_error: Exception):
        self.version = version
        self.name = name
        self.original_error = original_error
        super().__init__(f"Failed to apply migration {version:04d}_{name}: {original_error}")


async def run_migrations(dsn: str, migrations_dir: str = "migrations") -> List[Dict]:
    """
    Run all pending migrations.
    
    Args:
        dsn: PostgreSQL connection string
        migrations_dir: Directory containing migration SQL files
        
    Returns:
        List of applied migration info: [{"version": 1, "name": "...", "applied_at": "..."}]
        
    Raises:
        MigrationError: When a migration fails to apply
        Exception: For other errors (connection, file reading, etc.)
    """
    # Parse migration files
    migrations = _parse_migration_files(migrations_dir)
    
    if not migrations:
        print("No migration files found.")
        return []
    
    # Connect to database and run migrations
    conn = await _connect_with_retry(dsn)
    try:
        # Create schema_migrations table if not exists
        await _ensure_migrations_table(conn)
        
        # Get already applied migrations
        applied_versions = await _get_applied_versions(conn)
        
        # Filter to pending migrations (sorted by version)
        pending_migrations = [
            (version, name, sql) 
            for version, name, sql in migrations 
            if version not in applied_versions
        ]
        
        if not pending_migrations:
            print("No pending migrations.")
            return []
        
        print(f"Migration runner started. Found {len(pending_migrations)} pending migrations.")
        
        applied = []
        for version, name, sql in sorted(pending_migrations, key=lambda x: x[0]):
            print(f"  Applying {version:04d}_{name}...", end=" ", flush=True)
            
            try:
                # Use advisory lock to prevent concurrent migrations
                lock_key = 123456  # Arbitrary lock key for migration
                await conn.execute("SELECT pg_advisory_lock($1)", lock_key)
                
                # Run migration in a transaction
                async with conn.transaction():
                    await conn.execute(sql)
                    await _record_migration(conn, version, name)
                
                # Release advisory lock
                await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
                
                print("OK")
                applied.append({
                    "version": version,
                    "name": name,
                    "applied_at": datetime.now(timezone.utc).isoformat()
                })
                
            except asyncpg.PostgresError as e:
                await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
                print("FAILED")
                raise MigrationError(version, name, e)
            except Exception as e:
                # Ensure lock is released even for non-db errors
                try:
                    await conn.execute("SELECT pg_advisory_unlock($1)", lock_key)
                except Exception:
                    pass
                print("FAILED")
                raise MigrationError(version, name, e)
        
        print(f"{len(applied)} migrations applied successfully.")
        return applied
        
    finally:
        await conn.close()


def _parse_migration_files(migrations_dir: str) -> List[Tuple[int, str, str]]:
    """Parse migration files from directory."""
    migrations = []
    dir_path = Path(migrations_dir)
    
    if not dir_path.exists():
        raise ValueError(f"Migration directory '{migrations_dir}' does not exist")
    
    pattern = re.compile(r'^(\d{4})_(.*)\.sql$')
    
    for file_path in sorted(dir_path.glob('*.sql')):
        match = pattern.match(file_path.name)
        if not match:
            print(f"Warning: Skipping invalid migration file name: {file_path.name}")
            continue
        
        version = int(match.group(1))
        name = match.group(2)
        
        try:
            sql = file_path.read_text()
            migrations.append((version, name, sql))
        except Exception as e:
            raise ValueError(f"Failed to read migration file {file_path}: {e}")
    
    # Check for version gaps
    versions = [v for v, _, _ in migrations]
    if versions:
        expected_versions = list(range(min(versions), max(versions) + 1))
        missing = set(expected_versions) - set(versions)
        if missing:
            raise ValueError(f"Missing migration versions: {sorted(missing)}")
    
    return migrations


async def _connect_with_retry(dsn: str, max_retries: int = 3, delay: float = 5.0) -> asyncpg.Connection:
    """Connect to PostgreSQL with retry logic."""
    for attempt in range(max_retries):
        try:
            conn = await asyncpg.connect(dsn)
            return conn
        except (asyncpg.PostgresConnectionError, OSError) as e:
            if attempt == max_retries - 1:
                raise
            print(f"Connection attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
    
    raise asyncpg.PostgresConnectionError(f"Failed to connect after {max_retries} attempts")


async def _ensure_migrations_table(conn: asyncpg.Connection) -> None:
    """Create schema_migrations table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)


async def _get_applied_versions(conn: asyncpg.Connection) -> set:
    """Get set of already applied migration versions."""
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {row['version'] for row in rows}


async def _record_migration(conn: asyncpg.Connection, version: int, name: str) -> None:
    """Record a migration as applied."""
    await conn.execute(
        "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
        version, name
    )


def _get_dsn_from_env() -> str:
    """Get DATABASE_URL from environment with fallback."""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        # Try a default for development
        dsn = "postgresql://postgres:postgres@localhost:5432/didyouknow"
        print(f"Warning: DATABASE_URL not set, using default: {dsn}")
    return dsn


async def main() -> None:
    """CLI entry point."""
    try:
        dsn = _get_dsn_from_env()
        migrations_dir = "migrations"
        
        applied = await run_migrations(dsn, migrations_dir)
        
        if applied:
            print("\nApplied migrations:")
            for mig in applied:
                print(f"  {mig['version']:04d}: {mig['name']}")
        
    except MigrationError as e:
        print(f"\nMigration failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())