"""APScheduler integration for automated content pipeline execution.

Provides:
- ``scheduler``: Global AsyncIOScheduler instance
- ``setup_scheduler()``: Configure and add pipeline job
- ``run_pipeline()``: Full pipeline orchestration across all modules
- ``update_generation_state()``: Persist generation progress
- ``get_generation_state()``: Read current generation state
- ``reset_generation_state()``: Reset state to idle
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from shared.db import execute, fetch_one

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


# ===================================================================
# Generation state helpers
# ===================================================================


async def _ensure_generation_state_table(pool: Any) -> bool:
    """Check if generation_state table exists; return True if it does."""
    try:
        row = await fetch_one(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'generation_state') AS exists",
        )
        return row is not None and row["exists"]
    except Exception:
        return False


async def update_generation_state(
    pool: Any,
    status: str,
    progress_message: str | None = None,
    error_message: str | None = None,
) -> None:
    """UPSERT the single generation_state row.

    Args:
        pool: An asyncpg connection pool.
        status: One of ``idle``, ``running``, ``completed``, ``failed``.
        progress_message: Optional progress text.
        error_message: Optional error message (used when status is ``failed``).
    """
    try:
        async with pool.acquire() as conn:
            # Check if row exists
            row = await conn.fetchrow("SELECT id FROM generation_state LIMIT 1")
            if row:
                await conn.execute(
                    "UPDATE generation_state SET status = $1, "
                    "progress_message = COALESCE($2, progress_message), "
                    "error_message = COALESCE($3, error_message), "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = $4",
                    status, progress_message, error_message, row["id"],
                )
            else:
                await conn.execute(
                    "INSERT INTO generation_state (status, progress_message, error_message) "
                    "VALUES ($1, $2, $3)",
                    status, progress_message, error_message,
                )
    except Exception:
        logger.exception("Failed to update generation state")
        # Gracefully ignore if table doesn't exist yet


async def get_generation_state(pool: Any) -> dict[str, Any]:
    """Return the current generation state dict.

    Returns:
        Dict with keys ``status``, ``progress_message``, ``updated_at``.
        If the table doesn't exist, returns a default idle state.
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, progress_message, error_message, updated_at "
                "FROM generation_state LIMIT 1",
            )
            if row:
                return {
                    "status": row["status"],
                    "progress_message": row.get("progress_message") or "",
                    "error_message": row.get("error_message") or "",
                    "updated_at": (
                        row["updated_at"].isoformat()
                        if row["updated_at"]
                        else ""
                    ),
                }
    except Exception:
        logger.exception("Failed to get generation state")
    return {
        "status": "idle",
        "progress_message": "",
        "error_message": "",
        "updated_at": "",
    }


async def reset_generation_state(pool: Any) -> None:
    """Reset the generation state to idle."""
    await update_generation_state(pool, "idle", "No generation running", None)


def setup_scheduler(
    db_pool: Any,
    openrouter_client: Any,
    config: dict[str, Any],
) -> None:
    """Configure and add the content pipeline job to the scheduler.

    The pipeline runs every 2 hours with a single-instance constraint
    to prevent overlaps.  A misfire grace time of 5 minutes allows
    late execution if the system was temporarily unavailable.

    Args:
        db_pool: An asyncpg connection pool.
        openrouter_client: An OpenRouterClient instance.
        config: Dict with keys ``content_template``, ``platforms``,
            ``backup_trends`` (each is a config dict).
    """
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
            "config": config,
        },
    )
    logger.info("Scheduler configured: pipeline runs every 2 hours")


async def run_pipeline(
    db_pool: Any,
    openrouter_client: Any,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Execute the full content generation pipeline.

    Steps:
    1. Trend Selector — fetch trending topic
    2. Theme Associator — create theme from trend
    3. Content Generator — generate platform-specific options
    4. Visual Generator — generate images for options
    5. (Human approval happens via Web UI — TKT-011 deferred)

    Updates the generation_state table with progress at each step.

    Args:
        db_pool: An asyncpg connection pool.
        openrouter_client: An OpenRouterClient instance.
        config: Dict with config keys.

    Returns:
        Dict with pipeline execution result:
        ``{"status": "completed"|"skipped", "trend": ..., "theme": ...,
        "platforms": [...], "options_generated": N}``
    """
    from modules.trend_selector import TrendSelector
    from modules.theme_associator import ThemeAssociator
    from modules.content_generator import ContentGenerator
    from modules.visual_generator import VisualGenerator

    logger.info("Pipeline execution started")
    await update_generation_state(db_pool, "running", "Selecting trend...")

    # Step 1: Select trend
    trend_selector = TrendSelector(db_pool, config.get("backup_trends", {}))
    trend = await trend_selector.run()
    if not trend:
        logger.warning("Pipeline skipped: no trend found")
        await update_generation_state(
            db_pool, "failed", "No trend found",
            error_message="No trend found",
        )
        return {"status": "skipped", "reason": "no_trend_found"}

    logger.info("Pipeline step 1 complete: trend=%r", trend.keyword)
    await update_generation_state(db_pool, "running", "Creating theme...")

    # Step 2: Create theme
    theme_associator = ThemeAssociator(
        db_pool, openrouter_client, config.get("content_template", {})
    )
    theme = await theme_associator.run(trend)

    logger.info("Pipeline step 2 complete: theme=%r", theme.name)
    await update_generation_state(db_pool, "running", "Generating content...")

    # Determine enabled platforms from config
    platforms_config = config.get("platforms", {}).get("platforms", {})
    enabled_platforms = [
        p for p, cfg in platforms_config.items() if cfg.get("enabled", False)
    ]
    if not enabled_platforms:
        logger.warning("Pipeline skipped: no platforms enabled")
        await update_generation_state(
            db_pool, "failed", "No platforms enabled",
            error_message="No platforms enabled",
        )
        return {"status": "skipped", "reason": "no_platforms_enabled"}

    logger.info("Enabled platforms: %s", enabled_platforms)

    # Step 3: Generate content options for each enabled platform
    # Merge queue config from backup_trends into content_template config
    content_template_config = dict(config.get("content_template", {}))
    backup_config = config.get("backup_trends", {})
    if "queue" in backup_config:
        content_template_config["queue"] = backup_config["queue"]

    content_generator = ContentGenerator(
        db_pool, openrouter_client, content_template_config
    )
    options = await content_generator.run(theme, enabled_platforms)
    if not options:
        logger.warning("Pipeline skipped: queue full or no options generated")
        await update_generation_state(
            db_pool, "failed", "Queue full, no new content needed",
            error_message="Queue full, no new content needed",
        )
        return {"status": "skipped", "reason": "queue_full"}

    logger.info(
        "Pipeline step 3 complete: %d options generated", len(options)
    )

    # Step 4: Generate images
    await update_generation_state(
        db_pool, "running", "Generating images...",
    )
    visual_generator = VisualGenerator(
        db_pool, openrouter_client, config.get("platforms", {})
    )
    option_ids = [o.id for o in options if o.id is not None]
    await visual_generator.run(option_ids)

    logger.info(
        "Pipeline step 4 complete: images generated for %d options",
        len(option_ids),
    )

    result = {
        "status": "completed",
        "trend": trend.keyword,
        "theme": theme.name,
        "platforms": enabled_platforms,
        "options_generated": len(options),
    }
    logger.info("Pipeline execution complete: %s", result)

    await update_generation_state(
        db_pool,
        "completed",
        f"Pipeline complete! {len(options)} options generated for {len(enabled_platforms)} platforms",
    )
    return result
