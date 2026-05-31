# Database Schema & Migration Runner

## 1. Feature Overview
**Purpose**: Create PostgreSQL database schema for the AI Content Channel and a migration runner to manage schema versions
**Business Value**: Foundation for all data persistence — trends, themes, content options, and posts
**Scope**: Define 4 tables (trends, themes, content_options, posts) with indexes, constraints, triggers; build a migration runner that tracks applied migrations
**Success Criteria**: All tables created with proper FK relationships, `schema_migrations` tracking table works, runner applies migrations sequentially

## 2. Service Ownership
**Primary Service**: `shared/` (database infrastructure used by all modules)
**Dependent Services**: All modules (trend_selector, theme_associator, content_generator, visual_generator, platform_poster, web UI)
**Interface Changes**: New tables available for all services

## 3. Detailed Implementation

### Database Schema

**Location**: `migrations/0001_create_trends.sql`, `0002_create_themes.sql`, `0003_create_content.sql`, `0004_create_posts.sql`

#### Migration 0001: Trends Table
```sql
-- migrations/0001_create_trends.sql
CREATE TABLE IF NOT EXISTS trends (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    score DECIMAL(5,2) NOT NULL DEFAULT 0.0,
    source VARCHAR(50) NOT NULL DEFAULT 'google_trends',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trends_keyword ON trends(keyword);
CREATE INDEX idx_trends_created_at ON trends(created_at DESC);
CREATE INDEX idx_trends_score ON trends(score DESC);
```

#### Migration 0002: Themes Table
```sql
-- migrations/0002_create_themes.sql
CREATE TABLE IF NOT EXISTS themes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    trend_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_themes_trend_id FOREIGN KEY (trend_id)
        REFERENCES trends(id) ON DELETE CASCADE
);

CREATE INDEX idx_themes_name ON themes(name);
CREATE INDEX idx_themes_created_at ON themes(created_at DESC);
CREATE INDEX idx_themes_trend_id ON themes(trend_id);
```

#### Migration 0003: Content Options Table
```sql
-- migrations/0003_create_content.sql
CREATE TABLE IF NOT EXISTS content_options (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    theme VARCHAR(100) NOT NULL,
    fact TEXT NOT NULL,
    hashtags JSONB NOT NULL DEFAULT '[]',
    image_prompt TEXT,
    image_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'posted', 'expired', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_content_options_status ON content_options(status);
CREATE INDEX idx_content_options_batch_id ON content_options(batch_id);
CREATE INDEX idx_content_options_created_at ON content_options(created_at DESC);
CREATE INDEX idx_content_options_theme ON content_options(theme);
CREATE INDEX idx_content_options_platform ON content_options(platform);
CREATE INDEX idx_content_options_platform_status ON content_options(platform, status);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_content_options_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_content_options_updated_at
    BEFORE UPDATE ON content_options
    FOR EACH ROW EXECUTE FUNCTION update_content_options_updated_at();
```

#### Migration 0004: Posts Table
```sql
-- migrations/0004_create_posts.sql
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    content_option_id INTEGER NOT NULL,
    platform VARCHAR(50) NOT NULL,
    image_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'success', 'failed')),
    post_url TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_posts_content_option FOREIGN KEY (content_option_id)
        REFERENCES content_options(id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_content_option_id ON posts(content_option_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_platform ON posts(platform);
CREATE INDEX idx_posts_created_at ON posts(created_at DESC);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_posts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_posts_updated_at();
```

#### Migration Tracking Table
```sql
-- Created automatically by migrate.py
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Migration Runner (`shared/migrate.py`)

**Responsibilities**:
1. Connect to PostgreSQL using `DATABASE_URL` from environment
2. Create `schema_migrations` table if not exists
3. Scan `migrations/` directory for `NNNN_*.sql` files
4. Query `schema_migrations` for already-applied versions
5. Apply pending migrations in order (within a transaction each)
6. Record each applied migration in `schema_migrations`
7. Log progress to stdout

**Interface**:
```python
# shared/migrate.py

async def run_migrations(dsn: str, migrations_dir: str = "migrations") -> list[dict]:
    """
    Run all pending migrations.
    Returns list of applied migration info: [{"version": 1, "name": "...", "applied_at": "..."}]
    Raises MigrationError on failure.
    """

class MigrationError(Exception):
    """Raised when a migration fails to apply."""
    def __init__(self, version: int, name: str, original_error: Exception):
        self.version = version
        self.name = name
        self.original_error = original_error
```

**CLI Usage**:
```bash
python -m shared.migrate
# or
python main.py migrate
```

## 4. Error Handling
**Expected Failures**:
- Database connection refused (wrong host/port/credentials)
- Migration SQL syntax error
- Migration already partially applied (interrupted run)
- Concurrent migration runs
- Insufficient permissions (no CREATE TABLE)

**Recovery Strategies**:
- Connection failure: Retry 3 times with 5s delay, then fail with clear message
- SQL error: Rollback transaction, log failing SQL, raise MigrationError
- Partial apply: Each migration runs in a transaction — atomic, no partial state
- Concurrent runs: Use `advisory_lock` in PostgreSQL to prevent concurrent migration
- Permission error: Log clear message listing required permissions

**Error Responses**:
```
MigrationError: Failed to apply migration 0002_create_themes.sql:
  relation "trends" does not exist
```

**Logging Requirements**:
- INFO: Migration runner started, each migration applied successfully
- WARNING: No pending migrations found
- ERROR: Migration failure with full SQL error detail

## 5. Input/Output Specifications
**Input Validation**:
- Migration files must match pattern `NNNN_*.sql` (4-digit prefix)
- Version numbers must be sequential (no gaps)
- SQL must be valid PostgreSQL syntax

**Output Formats**:
```
Migration runner started.
  Applying 0001_create_trends.sql... OK
  Applying 0002_create_themes.sql... OK
  Applying 0003_create_content.sql... OK
  Applying 0004_create_posts.sql... OK
4 migrations applied successfully.
```

## 6. Edge Cases
- Migration directory empty (no files)
- Migration file has zero-padded vs non-zero-padded version numbers
- Database already has tables but no `schema_migrations` (manual setup)
- Migration file deleted after being recorded in `schema_migrations`
- Very large SQL file (timeout consideration)

## 7. Dependencies
- PostgreSQL 13+
- `asyncpg` library for async database access
- `DATABASE_URL` environment variable

## 8. Testing Requirements
- **Unit tests**: Migration file parsing, version ordering, SQL validation
- **Integration tests**: Apply all 4 migrations to test database, verify schema
- **Idempotency test**: Run migrations twice, verify no errors
- **Failure test**: Inject bad SQL, verify rollback works
- **Concurrency test**: Run two migration processes simultaneously

## 9. Deployment Considerations
- **Migration**: Must run before any application code starts
- **Rollback**: Manual rollback SQL if needed (DROP TABLE in reverse order)
- **Monitoring**: Log migration duration and success/failure
- **Performance**: All 4 migrations should complete in < 5 seconds
- **Backup**: Take database backup before first migration in production
