"""Integration tests for the actual schema migrations."""
import asyncio
import asyncpg
import os
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.migrate import run_migrations


@pytest.mark.integration
class TestSchemaMigrations:
    """Integration tests for the actual schema migrations."""
    
    @pytest.fixture
    async def test_db_connection(self):
        """Create a test database connection."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn or "test" not in dsn:
            pytest.skip("Requires test database (DATABASE_URL with 'test')")
        
        try:
            conn = await asyncpg.connect(dsn)
            yield conn
            await conn.close()
        except (asyncpg.PostgresConnectionError, OSError) as e:
            pytest.skip(f"Database not available: {e}")
    
    @pytest.fixture
    async def clean_db(self, test_db_connection):
        """Clean the database before each test."""
        conn = test_db_connection
        
        # Drop all tables (except schema_migrations will be created by migrate)
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename != 'schema_migrations'
        """)
        
        for table in tables:
            await conn.execute(f'DROP TABLE IF EXISTS "{table["tablename"]}" CASCADE')
        
        # Also drop functions
        functions = await conn.fetch("""
            SELECT proname 
            FROM pg_proc 
            WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """)
        
        for func in functions:
            await conn.execute(f'DROP FUNCTION IF EXISTS {func["proname"]} CASCADE')
        
        # Clear schema_migrations if it exists
        await conn.execute("DROP TABLE IF EXISTS schema_migrations CASCADE")
        
        yield conn
    
    @pytest.mark.asyncio
    async def test_full_migration_sequence(self, clean_db):
        """Test applying all 4 migrations in sequence."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            pytest.skip("DATABASE_URL not set")
        
        # Run migrations from the actual migrations directory
        migrations_dir = Path(__file__).parent.parent / "migrations"
        applied = await run_migrations(dsn, str(migrations_dir))
        
        # Should have applied 4 migrations
        assert len(applied) == 4
        assert [m["version"] for m in applied] == [1, 2, 3, 4]
        
        # Connect and verify schema
        conn = clean_db
        
        # Verify schema_migrations table was created
        migrations = await conn.fetch("SELECT version, name FROM schema_migrations ORDER BY version")
        assert len(migrations) == 4
        assert migrations[0]["version"] == 1
        assert migrations[0]["name"] == "create_trends"
        assert migrations[1]["version"] == 2
        assert migrations[1]["name"] == "create_themes"
        assert migrations[2]["version"] == 3
        assert migrations[2]["name"] == "create_content"
        assert migrations[3]["version"] == 4
        assert migrations[3]["name"] == "create_posts"
    
    @pytest.mark.asyncio
    async def test_verify_tables_and_indexes(self, clean_db):
        """Verify all tables, indexes, and constraints are created correctly."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            pytest.skip("DATABASE_URL not set")
        
        # Apply migrations
        migrations_dir = Path(__file__).parent.parent / "migrations"
        await run_migrations(dsn, str(migrations_dir))
        
        conn = clean_db
        
        # Check tables exist
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        table_names = {t["tablename"] for t in tables}
        expected_tables = {"trends", "themes", "content_options", "posts", "schema_migrations"}
        assert table_names == expected_tables
        
        # Check trends table structure
        trends_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'trends'
            ORDER BY ordinal_position
        """)
        
        # Verify trends columns
        assert len(trends_columns) == 5
        assert trends_columns[0]["column_name"] == "id"
        assert trends_columns[1]["column_name"] == "keyword"
        assert trends_columns[2]["column_name"] == "score"
        assert trends_columns[3]["column_name"] == "source"
        assert trends_columns[4]["column_name"] == "created_at"
        
        # Check foreign key constraints
        fks = await conn.fetch("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name, kcu.column_name
        """)
        
        # Should have 2 foreign keys: themes.trend_id → trends.id and posts.content_option_id → content_options.id
        assert len(fks) == 2
        
        fk_tables_columns = {(fk["table_name"], fk["column_name"]) for fk in fks}
        assert ("themes", "trend_id") in fk_tables_columns
        assert ("posts", "content_option_id") in fk_tables_columns
    
    @pytest.mark.asyncio
    async def test_verify_check_constraints(self, clean_db):
        """Verify CHECK constraints on status columns."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            pytest.skip("DATABASE_URL not set")
        
        # Apply migrations
        migrations_dir = Path(__file__).parent.parent / "migrations"
        await run_migrations(dsn, str(migrations_dir))
        
        conn = clean_db
        
        # Test content_options status constraint
        # Valid values should work
        await conn.execute("""
            INSERT INTO content_options (batch_id, platform, theme, fact, status)
            VALUES ('test', 'twitter', 'test', 'test fact', 'pending')
        """)
        
        await conn.execute("""
            INSERT INTO content_options (batch_id, platform, theme, fact, status)
            VALUES ('test2', 'twitter', 'test', 'test fact', 'approved')
        """)
        
        # Invalid status should fail
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute("""
                INSERT INTO content_options (batch_id, platform, theme, fact, status)
                VALUES ('test3', 'twitter', 'test', 'test fact', 'invalid_status')
            """)
        
        # Test posts status constraint
        # Need to insert a content_option first for foreign key
        content_id = await conn.fetchval("""
            INSERT INTO content_options (batch_id, platform, theme, fact)
            VALUES ('post_test', 'twitter', 'test', 'test fact')
            RETURNING id
        """)
        
        # Valid values should work
        await conn.execute("""
            INSERT INTO posts (content_option_id, platform, status)
            VALUES ($1, 'twitter', 'pending')
        """, content_id)
        
        await conn.execute("""
            INSERT INTO posts (content_option_id, platform, status)
            VALUES ($1, 'twitter', 'success')
        """, content_id)
        
        # Invalid status should fail
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute("""
                INSERT INTO posts (content_option_id, platform, status)
                VALUES ($1, 'twitter', 'invalid_status')
            """, content_id)
    
    @pytest.mark.asyncio
    async def test_updated_at_triggers(self, clean_db):
        """Verify updated_at triggers work correctly."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            pytest.skip("DATABASE_URL not set")
        
        # Apply migrations
        migrations_dir = Path(__file__).parent.parent / "migrations"
        await run_migrations(dsn, str(migrations_dir))
        
        conn = clean_db
        
        # Test content_options trigger
        content_id = await conn.fetchval("""
            INSERT INTO content_options (batch_id, platform, theme, fact)
            VALUES ('trigger_test', 'twitter', 'test', 'test fact')
            RETURNING id
        """)
        
        # Get initial updated_at
        initial = await conn.fetchrow("""
            SELECT created_at, updated_at FROM content_options WHERE id = $1
        """, content_id)
        
        assert initial["created_at"] == initial["updated_at"]
        
        # Wait a moment and update
        await asyncio.sleep(0.1)
        await conn.execute("""
            UPDATE content_options SET fact = 'updated fact' WHERE id = $1
        """, content_id)
        
        # updated_at should be newer than created_at
        updated = await conn.fetchrow("""
            SELECT created_at, updated_at FROM content_options WHERE id = $1
        """, content_id)
        
        assert updated["updated_at"] > updated["created_at"]
        
        # Test posts trigger
        post_id = await conn.fetchval("""
            INSERT INTO posts (content_option_id, platform)
            VALUES ($1, 'twitter')
            RETURNING id
        """, content_id)
        
        # Get initial updated_at for post
        post_initial = await conn.fetchrow("""
            SELECT created_at, updated_at FROM posts WHERE id = $1
        """, post_id)
        
        assert post_initial["created_at"] == post_initial["updated_at"]
        
        # Wait and update
        await asyncio.sleep(0.1)
        await conn.execute("""
            UPDATE posts SET status = 'success' WHERE id = $1
        """, post_id)
        
        # updated_at should be newer
        post_updated = await conn.fetchrow("""
            SELECT created_at, updated_at FROM posts WHERE id = $1
        """, post_id)
        
        assert post_updated["updated_at"] > post_updated["created_at"]
    
    @pytest.mark.asyncio
    async def test_idempotency(self, clean_db):
        """Test that migrations can be run multiple times without issues."""
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            pytest.skip("DATABASE_URL not set")
        
        migrations_dir = Path(__file__).parent.parent / "migrations"
        
        # First run
        applied1 = await run_migrations(dsn, str(migrations_dir))
        assert len(applied1) == 4
        
        # Second run - should do nothing
        applied2 = await run_migrations(dsn, str(migrations_dir))
        assert len(applied2) == 0
        
        # Third run - should still do nothing
        applied3 = await run_migrations(dsn, str(migrations_dir))
        assert len(applied3) == 0