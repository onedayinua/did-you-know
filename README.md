# Did You Know? - AI Content Channel

An automated system that generates and posts interesting "did you know" content to social media platforms.

## Project Structure

```
did-you-know/
├── migrations/           # Database migration SQL files
├── shared/              # Shared utilities (database, etc.)
├── tests/               # Test files
├── docs/                # Documentation
├── board/               # Kanban board tickets
├── pyproject.toml       # Python project configuration
├── .env.example         # Example environment variables
├── .env.test            # Test environment variables
└── README.md            # This file
```

## Quick Start

1. **Clone and install dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

2. **Set up PostgreSQL database:**
   ```bash
   # Create database
   createdb didyouknow
   
   # Or create test database
   createdb didyouknow_test
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and API keys
   ```

4. **Run database migrations:**
   ```bash
   python -m shared.migrate
   ```

5. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

## Database Schema

The system uses 4 main tables:

1. **trends** - Trending topics/keywords from various sources
2. **themes** - Content themes associated with trends
3. **content_options** - Generated content with status tracking
4. **posts** - Published posts across platforms

See `migrations/` for the complete schema definition.

## Migration Runner

The migration runner (`shared/migrate.py`):
- Tracks applied migrations in `schema_migrations` table
- Applies migrations in order (0001 → 0002 → 0003 → 0004)
- Uses transactions for atomicity
- Prevents concurrent migrations with advisory locks

Run migrations:
```bash
# Using the module directly
python -m shared.migrate

# Or programmatically
from shared.migrate import run_migrations
await run_migrations("postgresql://user:pass@host/db")
```

## Development

### Setting up development environment

1. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run tests:
   ```bash
   pytest tests/ -v --cov=shared --cov-report=term-missing
   ```

4. Format code:
   ```bash
   black shared/ tests/
   isort shared/ tests/
   flake8 shared/ tests/
   ```

### Testing Strategy

- **Unit tests**: Test migration file parsing, error handling
- **Integration tests**: Test actual migration application to test database
- **Idempotency tests**: Verify migrations can be run multiple times

## License

MIT