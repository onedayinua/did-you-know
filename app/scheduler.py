"""APScheduler integration for automated content pipeline execution.

Provides:
- ``scheduler``: Global AsyncIOScheduler instance
- ``setup_scheduler()``: Configure and add pipeline job
- ``run_pipeline()``: Full pipeline orchestration across all modules
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


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

    # Step 1: Select trend
    trend_selector = TrendSelector(db_pool, config.get("backup_trends", {}))
    trend = await trend_selector.run()
    if not trend:
        logger.warning("Pipeline skipped: no trend found")
        return {"status": "skipped", "reason": "no_trend_found"}

    logger.info("Pipeline step 1 complete: trend=%r", trend.keyword)

    # Step 2: Create theme
    theme_associator = ThemeAssociator(
        db_pool, openrouter_client, config.get("content_template", {})
    )
    theme = await theme_associator.run(trend)

    logger.info("Pipeline step 2 complete: theme=%r", theme.name)

    # Determine enabled platforms from config
    platforms_config = config.get("platforms", {}).get("platforms", {})
    enabled_platforms = [
        p for p, cfg in platforms_config.items() if cfg.get("enabled", False)
    ]
    if not enabled_platforms:
        logger.warning("Pipeline skipped: no platforms enabled")
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
        return {"status": "skipped", "reason": "queue_full"}

    logger.info(
        "Pipeline step 3 complete: %d options generated", len(options)
    )

    # Step 4: Generate images
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
    return result
