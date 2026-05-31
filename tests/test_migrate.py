"""Tests for the migration runner."""
import asyncio
import pytest
import tempfile
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.migrate import run_migrations, MigrationError, _parse_migration_files


class TestMigrationParsing:
    """Test migration file parsing and validation."""
    
    def test_parse_valid_migration_files(self):
        """Test parsing valid migration files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid migration files
            migrations_dir = Path(tmpdir)
            
            # Migration 1
            m1 = migrations_dir / "0001_create_trends.sql"
            m1.write_text("CREATE TABLE trends (id SERIAL PRIMARY KEY);")
            
            # Migration 2
            m2 = migrations_dir / "0002_create_themes.sql"
            m2.write_text("CREATE TABLE themes (id SERIAL PRIMARY KEY);")
            
            migrations = _parse_migration_files(str(migrations_dir))
            
            assert len(migrations) == 2
            assert migrations[0][0] == 1
            assert migrations[0][1] == "create_trends"
            assert migrations[1][0] == 2
            assert migrations[1][1] == "create_themes"
    
    def test_skip_invalid_filename(self):
        """Test that invalid filenames are skipped with warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            migrations_dir = Path(tmpdir)
            
            # Invalid filename (no version prefix)
            invalid = migrations_dir / "create_trends.sql"
            invalid.write_text("CREATE TABLE trends (id SERIAL PRIMARY KEY);")
            
            # Valid migration
            valid = migrations_dir / "0001_create_trends.sql"
            valid.write_text("CREATE TABLE trends (id SERIAL PRIMARY KEY);")
            
            migrations = _parse_migration_files(str(migrations_dir))
            
            assert len(migrations) == 1
            assert migrations[0][0] == 1
    
    def test_detect_version_gaps(self):
        """Test detection of missing migration versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            migrations_dir = Path(tmpdir)
            
            # Create migrations with gaps (1, 3)
            m1 = migrations_dir / "0001_first.sql"
            m1.write_text("-- first")
            
            m3 = migrations_dir / "0003_third.sql"
            m3.write_text("-- third")
            
            with pytest.raises(ValueError, match="Missing migration versions"):
                _parse_migration_files(str(migrations_dir))
    
    def test_version_ordering(self):
        """Test that migrations are ordered by version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            migrations_dir = Path(tmpdir)
            
            # Create migrations out of order
            m2 = migrations_dir / "0002_second.sql"
            m2.write_text("-- second")
            
            m1 = migrations_dir / "0001_first.sql"
            m1.write_text("-- first")
            
            migrations = _parse_migration_files(str(migrations_dir))
            
            # Should be returned in sorted order
            assert migrations[0][0] == 1
            assert migrations[0][1] == "first"
            assert migrations[1][0] == 2
            assert migrations[1][1] == "second"


class TestMigrationRunner:
    """Test the migration runner integration."""
    
    @pytest.fixture
    def test_migrations_dir(self, tmp_path):
        """Create a test migrations directory."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        
        # Create our actual migrations for testing
        m1 = migrations_dir / "0001_create_trends.sql"
        m1.write_text("""
            CREATE TABLE trends (
                id SERIAL PRIMARY KEY,
                keyword VARCHAR(255) NOT NULL
            );
        """)
        
        m2 = migrations_dir / "0002_create_themes.sql"
        m2.write_text("""
            CREATE TABLE themes (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                trend_id INTEGER NOT NULL
            );
        """)
        
        return str(migrations_dir)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_apply_migrations_success(self, test_migrations_dir):
        """Test successful migration application."""
        # Note: This test requires a real PostgreSQL database
        # In CI, we'd use a test container. For now, we'll skip if no DB.
        dsn = os.getenv("DATABASE_URL")
        if not dsn or "test" not in dsn:
            pytest.skip("Requires test database (DATABASE_URL with 'test')")
        
        try:
            applied = await run_migrations(dsn, test_migrations_dir)
            
            # Should have applied 2 migrations
            assert len(applied) == 2
            assert applied[0]["version"] == 1
            assert applied[1]["version"] == 2
            
            # Should be idempotent
            applied_again = await run_migrations(dsn, test_migrations_dir)
            assert len(applied_again) == 0  # No new migrations
            
        except Exception as e:
            if "connection" in str(e).lower() or "connect" in str(e).lower():
                pytest.skip(f"Database not available: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_migration_error_handling(self, tmp_path):
        """Test error handling for bad migration SQL."""
        # This test needs a real database connection to test SQL error handling
        # Skip if no test database available
        dsn = os.getenv("DATABASE_URL")
        if not dsn or "test" not in dsn:
            pytest.skip("Requires test database (DATABASE_URL with 'test')")
        
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        
        # Create first valid migration to ensure we can connect and create schema_migrations
        valid_migration = migrations_dir / "0001_valid.sql"
        valid_migration.write_text("CREATE TABLE test_table (id SERIAL PRIMARY KEY);")
        
        # Create second migration with invalid SQL
        bad_migration = migrations_dir / "0002_bad_sql.sql"
        bad_migration.write_text("INVALID SQL SYNTAX;")
        
        try:
            # Should raise MigrationError when it hits the invalid SQL
            with pytest.raises(MigrationError) as exc_info:
                await run_migrations(dsn, str(migrations_dir))
            
            # Should contain original error info
            assert exc_info.value.version == 2
            assert exc_info.value.name == "bad_sql"
            # Should be a PostgresError about syntax
            assert "syntax" in str(exc_info.value.original_error).lower()
            
        except Exception as e:
            if "connection" in str(e).lower() or "connect" in str(e).lower():
                pytest.skip(f"Database not available: {e}")
            raise
    
    def test_migration_error_class(self):
        """Test MigrationError exception formatting."""
        original_error = ValueError("Test error")
        error = MigrationError(42, "test_migration", original_error)
        
        assert error.version == 42
        assert error.name == "test_migration"
        assert error.original_error == original_error
        assert "Failed to apply migration 0042_test_migration" in str(error)


class TestConnectionRetry:
    """Test connection retry logic."""
    
    @pytest.mark.asyncio
    async def test_connection_retry_logic(self):
        """Test the retry logic (mocked)."""
        # This would test the retry logic with mocked asyncpg
        # For now, just verify the function exists and has correct signature
        from shared.migrate import _connect_with_retry
        
        # Test that it expects the right parameters
        import inspect
        sig = inspect.signature(_connect_with_retry)
        params = list(sig.parameters.keys())
        assert params == ['dsn', 'max_retries', 'delay']