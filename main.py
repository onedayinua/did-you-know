#!/usr/bin/env python3
"""CLI entrypoint for the Did You Know content channel.

Commands:
- ``migrate`` — Run database migrations
- ``serve`` — Start the FastAPI web server (with APScheduler)
- ``generate`` — Run the content pipeline once (manual execution)
"""

from __future__ import annotations

import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler

import click

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Suppress httpx INFO logging — it prints full HTTP response HTML to stdout
logging.getLogger("httpx").setLevel(logging.WARNING)

# File-based logging for pipeline debugging
os.makedirs("logs", exist_ok=True)
file_handler = RotatingFileHandler(
    "logs/pipeline.log",
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=3,
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logging.getLogger().addHandler(file_handler)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Did You Know — AI Content Channel CLI."""
    pass


@cli.command()
def migrate():
    """Run database migrations.

    Reads ``DATABASE_URL`` from environment and applies all pending
    migrations from the ``migrations/`` directory.
    """
    from shared.migrate import run_migrations

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        click.echo("ERROR: DATABASE_URL environment variable is not set.", err=True)
        raise click.Abort()

    click.echo("Running database migrations...")
    asyncio.run(run_migrations(dsn))
    click.echo("Migrations complete.")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host address")
@click.option("--port", default=8000, type=int, help="Bind port number")
@click.option("--reload", is_flag=True, help="Enable auto-reload (development mode)")
def serve(host: str, port: int, reload: bool):
    """Start the FastAPI web server with APScheduler.

    The server serves the content management dashboard on the specified
    host and port.  The APScheduler runs the content pipeline every 2 hours.
    """
    import uvicorn

    click.echo(f"Starting server on {host}:{port} (reload={reload})")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@cli.command()
def generate():
    """Run the content pipeline once (manual execution).

    Executes the full pipeline: trend selection → theme creation →
    content generation → image generation.  Results are printed to stdout.
    """
    from shared.db import init_pool, close_pool, get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import load_config
    from app.scheduler import run_pipeline

    async def _run():
        await init_pool()
        pool = await get_pool()

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            click.echo("ERROR: OPENROUTER_API_KEY environment variable is not set.", err=True)
            await close_pool()
            raise click.Abort()

        client = OpenRouterClient(api_key)
        config = {
            "content_template": load_config("content_template"),
            "platforms": load_config("platforms"),
            "backup_trends": load_config("backup_trends"),
        }

        click.echo("Running content pipeline...")
        result = await run_pipeline(pool, client, config)

        status = result.get("status", "unknown")
        if status == "completed":
            click.echo(
                f"Pipeline complete: trend={result.get('trend')!r} "
                f"theme={result.get('theme')!r} "
                f"platforms={result.get('platforms')} "
                f"options={result.get('options_generated')}"
            )
        else:
            click.echo(f"Pipeline skipped: {result.get('reason', 'unknown')}")

        await client.close()
        await close_pool()

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
