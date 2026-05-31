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
        - (Scheduler will be added in TKT-012)

    Shutdown:
        - Close DB pool gracefully
    """
    # Startup
    from shared.db import init_pool

    await init_pool()
    logger.info("Application started")

    yield

    # Shutdown
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
