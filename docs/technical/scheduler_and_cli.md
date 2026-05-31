# APScheduler & CLI Entrypoint

## 1. Feature Overview
**Purpose**: Orchestrate the content pipeline with scheduled jobs and provide CLI commands for manual operations
**Business Value**: Automates the 2-hour content generation cycle, provides manual control via CLI
**Scope**: APScheduler integration in FastAPI lifespan, `app/scheduler.py` for job definitions, `main.py` CLI entrypoint
**Success Criteria**: Scheduler runs pipeline every 2 hours, CLI commands work for manual generation and server start

## 2. Service Ownership
**Primary Service**: `app/scheduler.py`, `main.py`
**Dependent Services**: All modules (orchestrates the full pipeline)
**Interface Changes**: CLI commands (`generate`, `serve`, `migrate`)

## 3. Detailed Implementation

### APScheduler Integration (`app/scheduler.py`)

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler()

def setup_scheduler(db_pool, openrouter_client, config: dict):
    """Configure and add jobs to the scheduler."""

    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(hours=2),
        id="content_pipeline",
        name="Content Generation Pipeline",
        max_instances=1,
        misfire_grace_time=300,  # 5 minutes
        replace_existing=True,
        kwargs={
            "db_pool": db_pool,
            "openrouter_client": openrouter_client,
            "config": config
        }
    )

async def run_pipeline(db_pool, openrouter_client, config: dict):
    """
    Full pipeline execution.

    Steps:
    1. Trend Selector → get trend
    2. Theme Associator → create theme
    3. For each enabled platform:
       Content Generator → generate platform-specific options
    4. Visual Generator → generate images (platform-specific dimensions)
    5. (Human approval happens via Web UI)
    """
    from modules.trend_selector import TrendSelector
    from modules.theme_associator import ThemeAssociator
    from modules.content_generator import ContentGenerator
    from modules.visual_generator import VisualGenerator

    # Step 1: Select trend
    trend_selector = TrendSelector(db_pool, config.get("backup_trends", {}))
    trend = await trend_selector.run()
    if not trend:
        return {"status": "skipped", "reason": "no_trend_found"}

    # Step 2: Create theme
    theme_associator = ThemeAssociator(db_pool, openrouter_client, config.get("content_template", {}))
    theme = await theme_associator.run(trend)

    # Determine enabled platforms from config
    platforms_config = config.get("platforms", {}).get("platforms", {})
    enabled_platforms = [p for p, cfg in platforms_config.items() if cfg.get("enabled", False)]
    if not enabled_platforms:
        return {"status": "skipped", "reason": "no_platforms_enabled"}

    # Step 3: Generate content options for each enabled platform
    content_generator = ContentGenerator(db_pool, openrouter_client, config.get("content_template", {}))
    options = await content_generator.run(theme, enabled_platforms)
    if not options:
        return {"status": "skipped", "reason": "queue_full"}

    # Step 4: Generate images (platform-specific dimensions from option.platform)
    visual_generator = VisualGenerator(db_pool, openrouter_client, config.get("platforms", {}))
    option_ids = [o.id for o in options]
    await visual_generator.run(option_ids)

    return {
        "status": "completed",
        "trend": trend.keyword,
        "theme": theme.name,
        "platforms": enabled_platforms,
        "options_generated": len(options)
    }
```

### FastAPI Lifespan Integration (`app/main.py`)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.scheduler import scheduler, setup_scheduler
from shared.db import init_pool, close_pool
from shared.openrouter_client import OpenRouterClient
from shared.config_loader import load_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup
    await init_pool()

    # Initialize OpenRouter client
    api_key = os.environ.get("OPENROUTER_API_KEY")
    openrouter_client = OpenRouterClient(api_key)

    # Load configs
    content_config = load_config("content_template")
    platforms_config = load_config("platforms")
    backup_config = load_config("backup_trends")

    # Setup and start scheduler
    from shared.db import get_pool
    pool = await get_pool()
    setup_scheduler(pool, openrouter_client, {
        "content_template": content_config,
        "platforms": platforms_config,
        "backup_trends": backup_config
    })
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown()
    await openrouter_client.close()
    await close_pool()
```

### CLI Entrypoint (`main.py`)

```python
import asyncio
import click

@click.group()
def cli():
    """Did You Know - AI Content Channel CLI."""
    pass

@cli.command()
def migrate():
    """Run database migrations."""
    from shared.migrate import run_migrations
    dsn = os.environ.get("DATABASE_URL")
    asyncio.run(run_migrations(dsn))

@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--reload", is_flag=True, help="Enable auto-reload (dev mode)")
def serve(host: str, port: int, reload: bool):
    """Start FastAPI server with APScheduler."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    )

@cli.command()
def generate():
    """Run content pipeline once (outside scheduler)."""
    from app.scheduler import run_pipeline
    from shared.db import init_pool, close_pool, get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import load_config

    async def _run():
        await init_pool()
        pool = await get_pool()
        api_key = os.environ.get("OPENROUTER_API_KEY")
        client = OpenRouterClient(api_key)
        config = {
            "content_template": load_config("content_template"),
            "platforms": load_config("platforms"),
            "backup_trends": load_config("backup_trends")
        }
        result = await run_pipeline(pool, client, config)
        print(result)
        await client.close()
        await close_pool()

    asyncio.run(_run())

if __name__ == "__main__":
    cli()
```

### Project Dependencies (`pyproject.toml`)

```toml
[project]
name = "did-you-know"
version = "0.1.0"
description = "AI-driven culinary content channel"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.23.0",
    "jinja2>=3.1.0",
    "asyncpg>=0.28.0",
    "pydantic>=2.0.0",
    "httpx>=0.24.0",
    "pyyaml>=6.0",
    "pytrends>=4.9.0",
    "apscheduler>=3.10.0",
    "python-dotenv>=1.0.0",
    "click>=8.0.0",
]

[project.scripts]
did-you-know = "main:cli"
```

## 4. Error Handling
**Expected Failures**:
- Scheduler job overlap (previous run still running)
- Module failure during pipeline
- CLI command with missing env vars
- Scheduler misfire (system was asleep/busy)

**Recovery Strategies**:
- Overlap: `max_instances=1` prevents it, logs warning
- Module failure: Log error, pipeline aborts for this cycle (retry in 2 hours)
- Missing env vars: Fail fast with clear message listing required vars
- Misfire: `misfire_grace_time=300` allows late execution within 5 min

**Logging Requirements**:
- INFO: Scheduler started, job executed, pipeline result
- WARNING: Job misfire, job skipped
- ERROR: Pipeline failure, scheduler error

## 5. Input/Output Specifications
**CLI Commands**:
```bash
python main.py migrate          # Run migrations
python main.py serve            # Start server
python main.py serve --reload   # Start with auto-reload
python main.py serve --port 9000 # Custom port
python main.py generate         # Manual pipeline run
```

**Scheduler Output**:
```json
{
    "status": "completed",
    "trend": "air fryer recipes",
    "theme": "Crispy Cooking",
    "platforms": ["pinterest", "instagram"],
    "options_generated": 6
}
```

## 6. Edge Cases
- Scheduler starts before DB pool initialized (lifespan order prevents)
- CLI command run without `.env` file
- Multiple serve processes (port conflict)
- Scheduler timezone vs system timezone
- Very slow pipeline (takes > 2 hours)

## 7. Dependencies
- `apscheduler` for job scheduling
- `click` for CLI
- `uvicorn` for ASGI server
- All modules (orchestrated)

## 8. Testing Requirements
- **Unit tests**: Test pipeline orchestration with mocked modules
- **Integration tests**: Full pipeline with test database
- **CLI tests**: Test each command with mocked dependencies
- **Scheduler tests**: Verify job scheduling configuration

## 9. Deployment Considerations
- **Migration**: Run `python main.py migrate` before starting server
- **Rollback**: Stop server, revert code
- **Monitoring**: Log pipeline execution count, duration, success rate
- **Performance**: Pipeline runs every 2 hours, ~60s per run
- **Process management**: Single process (FastAPI + scheduler in-process)
