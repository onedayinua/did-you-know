#!/usr/bin/env python3
"""
Database Connection Tool for OpenCode Agents

This tool provides read-only access to any service's database for debugging
and development purposes. It uses the existing shared/database.py connection
manager and supports multiple services via .env configuration.

Currently supports: SQLite, PostgreSQL

Usage:
    from .opencode.tools.database_tool import DatabaseTool
    
    # Create tool instance for a specific service
    db_tool = DatabaseTool(service_name="data-service")
    
    # OR create tool with direct database URL
    db_tool = DatabaseTool(database_url="sqlite+aiosqlite:///./mltscr.db")
    
    # Run a query
    result = await db_tool.query("SELECT * FROM assets LIMIT 5")
    
    # Get table schema
    schema = await db_tool.get_table_schema("ohlcv")
    
    # List all tables
    tables = await db_tool.list_tables()
    
    # Get row count
    count = await db_tool.get_row_count("assets")
    
    # Get database statistics
    stats = await db_tool.get_database_stats()
    
    # Use as async context manager
    async with DatabaseTool(service_name="data-service") as db_tool:
        result = await db_tool.query("SELECT * FROM assets")
"""

import asyncio
import json
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager

from sqlalchemy import text, select, func, Table, MetaData, inspect
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

# Add project root to path to import shared modules
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.database import Database
from shared.config import Config


class DatabaseTool:
    """Generic database connection tool for OpenCode agents to query any service database."""
    
    def __init__(
        self,
        service_name: Optional[str] = None,
        database_url: Optional[str] = None,
        echo: bool = False,
        timeout: float = 30.0,
        pool_size: int = 5
    ):
        """
        Initialize the database tool.
        
        Args:
            service_name: Name of service (e.g., "data-service", "trading-service")
            database_url: Direct database URL (alternative to service_name)
            echo: Whether to echo SQL queries (default: False)
            timeout: Connection timeout in seconds (default: 30.0)
            pool_size: Connection pool size (default: 5)
            
        Note: Either service_name OR database_url must be provided.
              If both are provided, service_name takes precedence.
        """
        self.service_name = service_name
        self.database_url = database_url
        self.echo = echo
        self.timeout = timeout
        self.pool_size = pool_size
        self.db: Optional[Database] = None
        self._initialized = False
        self._project_root = Path(__file__).resolve().parents[2]
        
        # Check for deprecated usage (no parameters)
        if service_name is None and database_url is None:
            warnings.warn(
                "Creating DatabaseTool without service_name or database_url is deprecated. "
                "Please specify service_name (e.g., DatabaseTool(service_name='data-service')) "
                "or database_url.",
                DeprecationWarning,
                stacklevel=2
            )
        
    def _get_database_type(self, url: str) -> str:
        """
        Determine database type from URL.
        
        Args:
            url: Database connection URL
            
        Returns:
            Database type: 'sqlite', 'postgresql', or 'unknown'
        """
        if url.startswith("sqlite"):
            return "sqlite"
        elif "postgresql" in url or "postgres" in url:
            return "postgresql"
        else:
            return "unknown"
    
    def _resolve_database_url(self, service_name: str, raw_url: str) -> str:
        """
        Resolve relative database paths relative to service directory.
        
        Args:
            service_name: Name of the service
            raw_url: Raw database URL from .env file
            
        Returns:
            Resolved database URL with absolute path
            
        Example:
            Input: "data-service", "sqlite+aiosqlite:///./mltscr.db"
            Output: "sqlite+aiosqlite:////workspaces/mltscr/data-service/mltscr.db"
        """
        db_type = self._get_database_type(raw_url)
        
        # Only resolve paths for SQLite (file-based databases)
        if db_type != "sqlite":
            return raw_url
        
        # Check if URL uses relative path (contains ./)
        if "./" in raw_url:
            service_dir = self._project_root / service_name
            if not service_dir.exists():
                raise ValueError(
                    f"Service directory '{service_name}' not found at {service_dir}"
                )
            
            # Extract the relative path from the URL
            # Format: sqlite+aiosqlite:///./path/to/db.db or sqlite:///./path/to/db.db
            match = re.search(r'sqlite\+?aiosqlite:///\.\/(.+)', raw_url)
            if match:
                relative_path = match.group(1)
                absolute_path = service_dir / relative_path
                # Replace relative path with absolute path
                resolved_url = raw_url.replace(f"./{relative_path}", str(absolute_path))
                return resolved_url
        
        return raw_url
    
    async def initialize(self) -> None:
        """Initialize database connection using service configuration or direct URL."""
        if self._initialized:
            return
            
        try:
            # Determine database URL
            if self.service_name:
                # Load service configuration
                config = Config(self.service_name)
                raw_url = config.get_required("DATABASE_URL")
                # Resolve relative paths
                database_url = self._resolve_database_url(self.service_name, raw_url)
            elif self.database_url:
                database_url = self.database_url
            else:
                raise ValueError("Either service_name or database_url must be provided")
            
            # Verify database file exists for SQLite
            if database_url.startswith("sqlite"):
                # Extract file path from URL
                # Format: sqlite+aiosqlite:///path/to/db.db
                match = re.search(r'sqlite\+?aiosqlite:///(.+)', database_url)
                if match:
                    db_path = Path(match.group(1))
                    if not db_path.exists():
                        raise FileNotFoundError(
                            f"Database file not found: {db_path}\n"
                            f"Service: {self.service_name}\n"
                            f"Expected path: {db_path}"
                        )
            
            # Create database connection using shared Database class
            self.db = Database(database_url, echo=self.echo)
            
            # Test connection
            await self.db.connect()
            self._initialized = True
            print(f"✅ Database tool initialized with service: {self.service_name or 'custom'}")
            print(f"   Database URL: {database_url}")
            
        except Exception as e:
            print(f"❌ Failed to initialize database tool: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None
            self._initialized = False
            print("✅ Database connection closed")
    
    async def _ensure_initialized(self) -> None:
        """Ensure database is initialized."""
        if not self._initialized:
            await self.initialize()
    
    async def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query and return results as dictionaries.
        
        Args:
            sql: SQL query string (read-only SELECT queries only)
            params: Optional query parameters
            
        Returns:
            List of dictionaries representing rows
            
        Raises:
            ValueError: If query contains non-SELECT statements or is unsafe
        """
        await self._ensure_initialized()
        
        # Validate SQL for read-only access
        self._validate_read_only_query(sql)
        
        try:
            async with self.db.session_factory() as session:
                # Use text() with parameters to prevent SQL injection
                result = await session.execute(text(sql), params or {})
                rows = result.fetchall()
                
                # Convert to list of dictionaries
                if rows:
                    columns = result.keys()
                    return [dict(zip(columns, row)) for row in rows]
                return []
                
        except Exception as e:
            print(f"❌ Query failed: {e}")
            raise
    
    def _validate_read_only_query(self, sql: str) -> None:
        """
        Validate that a SQL query is read-only and safe.
        
        Args:
            sql: SQL query string to validate
            
        Raises:
            ValueError: If query contains non-SELECT statements
        """
        # Normalize SQL for checking
        sql_upper = sql.strip().upper()
        
        # Remove comments
        sql_upper = re.sub(r'--.*$', '', sql_upper, flags=re.MULTILINE)
        sql_upper = re.sub(r'/\*.*?\*/', '', sql_upper, flags=re.DOTALL)
        
        # Check for dangerous keywords
        dangerous_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", 
            "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "MERGE",
            "REPLACE", "COMMIT", "ROLLBACK"
        ]
        
        for keyword in dangerous_keywords:
            # Use word boundaries to avoid matching within words
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                raise ValueError(
                    f"Query contains non-read-only keyword: {keyword}. "
                    f"Only SELECT queries are allowed."
                )
        
        # Ensure it starts with SELECT
        if not sql_upper.startswith("SELECT"):
            # Allow pragma and sqlite_master queries for SQLite
            if not (sql_upper.startswith("PRAGMA") or "SQLITE_MASTER" in sql_upper):
                raise ValueError(
                    "Query must start with SELECT, PRAGMA, or query sqlite_master. "
                    "Only read-only queries are allowed."
                )
    
    async def list_tables(self) -> List[str]:
        """List all tables in the database."""
        await self._ensure_initialized()
        
        # Get database type from URL
        db_type = self._get_database_type(self.db.url)
        
        if db_type == "sqlite":
            sql = """
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        elif db_type == "postgresql":
            sql = """
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        else:
            # Generic fallback using SQLAlchemy inspect
            try:
                async with self.db.engine.connect() as conn:
                    inspector = inspect(conn)
                    tables = await conn.run_sync(
                        lambda sync_conn: inspector.get_table_names(schema=None)
                    )
                    return [t for t in tables if not t.startswith("sqlite_") and not t.startswith("sql_")]
            except Exception as e:
                raise RuntimeError(f"Could not list tables for database type {db_type}: {e}")
        
        try:
            results = await self.query(sql)
            if db_type == "sqlite":
                return [row["name"] for row in results]
            else:  # postgresql
                return [row["tablename"] for row in results]
        except Exception as e:
            raise RuntimeError(f"Could not list tables: {e}")
    
    async def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
            
        Raises:
            ValueError: If table_name contains unsafe characters or doesn't exist
        """
        await self._ensure_initialized()
        
        # Validate table name to prevent SQL injection
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        
        # Check if table exists
        tables = await self.list_tables()
        if table_name not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in database")
        
        # Get database type from URL
        db_type = self._get_database_type(self.db.url)
        
        try:
            # Try SQLAlchemy inspect first (database-agnostic)
            async with self.db.engine.connect() as conn:
                inspector = inspect(conn)
                columns = await conn.run_sync(
                    lambda sync_conn: inspector.get_columns(table_name, schema=None)
                )
                
                return [
                    {
                        "name": col["name"],
                        "type": str(col["type"]) if col.get("type") else "unknown",
                        "nullable": col.get("nullable", True),
                        "default": str(col.get("default", "")) if col.get("default") else None,
                        "primary_key": bool(col.get("primary_key", 0))
                    }
                    for col in columns
                ]
                
        except Exception:
            # Fallback to database-specific queries
            try:
                # SQLite PRAGMA fallback
                sql = f"PRAGMA table_info({table_name})"
                return await self.query(sql)
            except Exception:
                try:
                    # PostgreSQL information_schema fallback - use parameterized query
                    sql = """
                    SELECT 
                        column_name as name,
                        data_type as type,
                        is_nullable as nullable,
                        column_default as default,
                        CASE WHEN column_name IN (
                            SELECT column_name FROM information_schema.key_column_usage 
                            WHERE table_name = :table_name AND constraint_name LIKE '%_pkey'
                        ) THEN 1 ELSE 0 END as primary_key
                    FROM information_schema.columns 
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                    """
                    return await self.query(sql, {"table_name": table_name})
                except Exception as e:
                    raise RuntimeError(
                        f"Could not get table schema. "
                        f"Please check your database connection. Error: {e}"
                    )
    
    async def get_row_count(self, table_name: str) -> int:
        """
        Get the number of rows in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Row count
            
        Raises:
            ValueError: If table_name contains unsafe characters or doesn't exist
        """
        # Validate table name to prevent SQL injection
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        
        # Check if table exists
        tables = await self.list_tables()
        if table_name not in tables:
            raise ValueError(f"Table '{table_name}' does not exist in database")
        
        # Use SQLAlchemy's Table reflection for safe table name handling
        # This prevents SQL injection even though table_name has been validated
        # We use a sync connection via run_sync since Table reflection requires it
        metadata = MetaData()
        
        try:
            async with self.db.engine.connect() as conn:
                # Use run_sync for table reflection (requires sync connection)
                table = await conn.run_sync(
                    lambda sync_conn: Table(table_name, metadata, autoload_with=sync_conn)
                )
                stmt = select(func.count()).select_from(table)
                result = await conn.execute(stmt)
                row = result.scalar()
                return row if row is not None else 0
        except Exception as e:
            raise RuntimeError(f"Could not get row count for table '{table_name}': {e}")
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        tables = await self.list_tables()
        stats = {
            "tables": tables,
            "table_counts": {}
        }
        
        for table in tables:
            try:
                count = await self.get_row_count(table)
                stats["table_counts"][table] = count
            except Exception as e:
                stats["table_counts"][table] = f"Error: {e}"
        
        return stats
    
    @asynccontextmanager
    async def session(self):
        """
        Context manager for database session.
        
        Usage:
            async with db_tool.session() as session:
                result = await session.execute(text("SELECT * FROM assets"))
                # ...
        """
        await self._ensure_initialized()
        async with self.db.session_factory() as session:
            yield session
    
    async def execute_and_print(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Execute a query and print formatted results.
        
        Args:
            sql: SQL query string
            params: Optional query parameters
        """
        results = await self.query(sql, params)
        
        if not results:
            print("No results found.")
            return
        
        # Print column headers
        columns = list(results[0].keys())
        print(" | ".join(columns))
        print("-" * (len(" | ".join(columns))))
        
        # Print rows
        for row in results:
            values = []
            for col in columns:
                value = row[col]
                if value is None:
                    values.append("NULL")
                elif isinstance(value, (int, float)):
                    values.append(str(value))
                else:
                    values.append(str(value)[:50])  # Truncate long strings
            print(" | ".join(values))
    
    async def __aenter__(self):
        """
        Async context manager entry.
        
        Usage:
            async with DatabaseTool(service_name='data-service') as db_tool:
                result = await db_tool.query("SELECT * FROM assets")
        """
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        """
        await self.close()


# Example usage when run directly
async def main():
    """Example usage of the database tool."""
    print("🔍 Starting database debug session...")
    print("\nNote: Specify service_name or database_url when creating DatabaseTool")
    print("Example: DatabaseTool(service_name='data-service')")
    
    tool = DatabaseTool(service_name="data-service", echo=False)
    
    try:
        # Get database stats
        print("\n📊 Database Statistics:")
        stats = await tool.get_database_stats()
        print(json.dumps(stats, indent=2))
        
        # List tables
        print(f"\n📋 Tables: {', '.join(stats['tables'])}")
        
        # Example raw query
        print("\n🔍 Example raw query (table schemas):")
        await tool.execute_and_print("SELECT name, sql FROM sqlite_master WHERE type='table'")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tool.close()


if __name__ == "__main__":
    asyncio.run(main())
