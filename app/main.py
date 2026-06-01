"""FastAPI application with lifespan management.

Initializes DB pool on startup, serves static images, and
mounts the API router with the content management dashboard.
"""

from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle.

    Startup:
        - Initialize DB pool from DATABASE_URL env var
        - Initialize OpenRouter client
        - Load all configs
        - Setup and start APScheduler

    Shutdown:
        - Shutdown scheduler gracefully
        - Close OpenRouter client
        - Close DB pool
    """
    # Startup
    from shared.db import init_pool, get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import load_config
    from app.scheduler import setup_scheduler, scheduler as apscheduler

    await init_pool()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_client = OpenRouterClient(api_key)

    content_config = load_config("content_template")
    platforms_config = load_config("platforms")
    backup_config = load_config("backup_trends")

    pool = await get_pool()
    setup_scheduler(pool, openrouter_client, {
        "content_template": content_config,
        "platforms": platforms_config,
        "backup_trends": backup_config,
    })
    apscheduler.start()

    logger.info("Application started with scheduler")

    yield

    # Shutdown
    apscheduler.shutdown()
    await openrouter_client.close()

    from shared.db import close_pool
    await close_pool()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Did You Know - Content Channel",
    description="AI-driven culinary content management dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount API routes
from app.routes import router  # noqa: E402

app.include_router(router)

# Serve static files (generated images)
os.makedirs("data/images", exist_ok=True)
app.mount("/images", StaticFiles(directory="data/images"), name="images")
