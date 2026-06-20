"""API routes for the content management dashboard.

Endpoints:
- GET  /                          — Dashboard with pending content options
- GET  /approved                  — Approved content options page
- GET  /options/{id}              — Option detail page
- POST /options/{id}/approve      — Approve a content option
- POST /options/{id}/cancel       — Cancel a content option
- POST /options/{id}/regenerate-text  — Regenerate fact + hashtags
- POST /options/{id}/regenerate-image — Regenerate image only
- GET  /preview/{id}              — Preview across all platforms
- GET  /preview/{id}/{platform}   — Preview for specific platform
- GET  /history                   — Posted content history
- GET  /health                    — Health check
- POST /generate                  — Trigger content generation pipeline
- POST /generate/reset            — Reset generation state to idle
- GET  /generate/status           — Get generation pipeline status
"""

from __future__ import annotations

import asyncio
import json as json_module
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from shared.db import fetch, fetch_one, execute, transaction

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ===================================================================
# Dashboard
# ===================================================================


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, platform: str | None = None):
    """Show all pending content options, optionally filtered by platform.

    Args:
        request: FastAPI request object.
        platform: Optional platform filter (``"pinterest"`` or ``"instagram"``).

    Returns:
        HTML dashboard page.
    """
    if platform:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'pending'
            AND platform = $1
            ORDER BY created_at DESC
        """
        rows = await fetch(query, platform)
    else:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """
        rows = await fetch(query)

    options = [_row_to_dict(r) for r in rows]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "options": options,
            "current_platform": platform,
        },
    )


# ===================================================================
# Approved Page
# ===================================================================


@router.get("/approved", response_class=HTMLResponse)
async def approved_page(request: Request, platform: str | None = None):
    """Show all approved content options, optionally filtered by platform.

    Args:
        request: FastAPI request object.
        platform: Optional platform filter (``"pinterest"`` or ``"instagram"``).

    Returns:
        HTML approved page.
    """
    if platform:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'approved'
            AND platform = $1
            ORDER BY created_at DESC
        """
        rows = await fetch(query, platform)
    else:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'approved'
            ORDER BY created_at DESC
        """
        rows = await fetch(query)

    options = [_row_to_dict(r) for r in rows]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "options": options,
            "current_platform": platform,
            "approved_mode": True,
        },
    )


# ===================================================================
# Posted Page
# ===================================================================


@router.get("/posted", response_class=HTMLResponse)
async def posted_page(request: Request, platform: str | None = None):
    """Show all posted content options, optionally filtered by platform.

    Args:
        request: FastAPI request object.
        platform: Optional platform filter (``"pinterest"`` or ``"instagram"``).

    Returns:
        HTML posted page.
    """
    if platform:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'posted'
            AND platform = $1
            ORDER BY created_at DESC
        """
        rows = await fetch(query, platform)
    else:
        query = """
            SELECT id, batch_id, platform, theme, fact, hashtags,
                   image_prompt, image_path, status, created_at, updated_at
            FROM content_options
            WHERE status = 'posted'
            ORDER BY created_at DESC
        """
        rows = await fetch(query)

    options = [_row_to_dict(r) for r in rows]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "options": options,
            "current_platform": platform,
            "posted_mode": True,
        },
    )


# ===================================================================
# Option Detail
# ===================================================================


@router.get("/options/{id}", response_class=HTMLResponse)
async def option_detail(request: Request, id: int):
    """Show full details of a single content option.

    Args:
        request: FastAPI request object.
        id: Content option ID.

    Returns:
        HTML detail page.

    Raises:
        HTTPException 404: If option not found.
    """
    row = await fetch_one(
        """
        SELECT id, batch_id, platform, theme, fact, hashtags,
               image_prompt, image_path, status, created_at, updated_at
        FROM content_options
        WHERE id = $1
        """,
        id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content option not found")

    option = _row_to_dict(row)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "options": [option],
            "current_platform": None,
            "detail_mode": True,
        },
    )


# ===================================================================
# Actions
# ===================================================================


@router.post("/options/{id}/approve")
async def approve_option(id: int):
    """Approve a content option — marks as ready for manual posting.

    Args:
        id: Content option ID.

    Returns:
        Redirect to dashboard.

    Raises:
        HTTPException 409: If option is not in ``pending`` status.
    """
    result = await execute(
        "UPDATE content_options SET status = 'approved', updated_at = CURRENT_TIMESTAMP "
        "WHERE id = $1 AND status = 'pending'",
        id,
    )
    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=409,
            detail="Option not found or not in pending status",
        )
    logger.info("Approved content option id=%d", id)
    return RedirectResponse(url="/", status_code=302)


@router.post("/options/{id}/cancel")
async def cancel_option(id: int, next: str = "/"):
    """Cancel a content option.

    Args:
        id: Content option ID.
        next: URL to redirect to after cancellation (default: "/").

    Returns:
        Redirect to the specified URL (or dashboard by default).

    Raises:
        HTTPException 409: If option is not in ``pending`` or ``approved`` status.
    """
    result = await execute(
        "UPDATE content_options SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP "
        "WHERE id = $1 AND status IN ('pending', 'approved')",
        id,
    )
    if "UPDATE 0" in result:
        raise HTTPException(
            status_code=409,
            detail="Option not found or not in pending/approved status",
        )
    logger.info("Cancelled content option id=%d", id)
    return RedirectResponse(url=next, status_code=302)


@router.post("/options/{id}/mark-posted")
async def mark_option_as_posted(id: int):
    """Mark an approved content option as posted.

    Creates a posts record and updates content_options status to 'posted'.

    Args:
        id: Content option ID.

    Returns:
        JSON with post_id on success.

    Raises:
        HTTPException 404: If option not found.
        HTTPException 409: If option is not in 'approved' status.
        HTTPException 500: If DB transaction fails.
    """
    # First check if the option exists at all
    exists = await fetch_one(
        "SELECT id FROM content_options WHERE id = $1",
        id,
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Content option not found")

    # Then check status
    row = await fetch_one(
        "SELECT id, platform, image_path FROM content_options "
        "WHERE id = $1 AND status = 'approved'",
        id,
    )
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Option not found or not in approved status",
        )

    try:
        async with transaction() as conn:
            post_row = await conn.fetchrow(
                "INSERT INTO posts (content_option_id, platform, image_path, status) "
                "VALUES ($1, $2, $3, 'success') "
                "RETURNING id",
                id,
                row["platform"],
                row.get("image_path"),
            )
            await conn.execute(
                "UPDATE content_options SET status = 'posted', updated_at = CURRENT_TIMESTAMP "
                "WHERE id = $1",
                id,
            )
    except Exception as e:
        logger.error("Mark-posted transaction failed for option %d: %s", id, e)
        raise HTTPException(status_code=500, detail="Failed to mark post as posted")

    logger.info("Marked option %d as posted, post_id=%d", id, post_row["id"])
    return {"status": "ok", "message": "Post marked as posted", "post_id": post_row["id"]}


@router.post("/options/{id}/regenerate-text")
async def regenerate_text(id: int):
    """Regenerate fact + hashtags for a content option, keeping the image.

    Requires the ContentGenerator module.  The option's theme is used
    to generate a new text variation.

    Args:
        id: Content option ID.

    Returns:
        Redirect to option detail page.

    Raises:
        HTTPException 404: If option not found.
        HTTPException 500: If regeneration fails.
    """
    row = await fetch_one(
        "SELECT id, theme, platform FROM content_options WHERE id = $1",
        id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content option not found")

    from shared.db import get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import get_content_template
    from modules.content_generator import ContentGenerator

    pool = await get_pool()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = OpenRouterClient(api_key)
    config = get_content_template()

    generator = ContentGenerator(pool, client, config)
    platform_limits = config.get("platforms", {}).get(row["platform"], {})
    variations = await generator._generate_text_variations(
        theme=row["theme"],
        count=1,
        platform_limits=platform_limits,
    )

    if not variations:
        await client.close()
        raise HTTPException(status_code=500, detail="Text regeneration failed")

    var = variations[0]
    hashtags_json = json_module.dumps(var["hashtags"])
    await execute(
        "UPDATE content_options SET fact = $1, hashtags = $2::jsonb, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = $3",
        var["fact"],
        hashtags_json,
        id,
    )
    await client.close()
    logger.info("Regenerated text for option id=%d", id)
    return RedirectResponse(url=f"/options/{id}", status_code=302)


@router.post("/options/{id}/regenerate-image")
async def regenerate_image(id: int):
    """Regenerate image for a content option, keeping the text.

    Requires the VisualGenerator module.  The option's existing
    ``image_prompt`` is used to generate a new image.

    Args:
        id: Content option ID.

    Returns:
        Redirect to option detail page.

    Raises:
        HTTPException 404: If option not found.
        HTTPException 500: If regeneration fails.
    """
    row = await fetch_one(
        "SELECT id, batch_id, platform, image_prompt FROM content_options WHERE id = $1",
        id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content option not found")
    if not row.get("image_prompt"):
        raise HTTPException(status_code=400, detail="Option has no image prompt")

    from shared.db import get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import get_platforms_config
    from modules.visual_generator import VisualGenerator

    pool = await get_pool()
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = OpenRouterClient(api_key)
    config = get_platforms_config()

    # Create a minimal ContentOption-like object for the generator
    from shared.models import ContentOption

    option = ContentOption(
        id=row["id"],
        batch_id=row["batch_id"],
        platform=str(row["platform"]),
        theme="",
        fact="",
        hashtags=[],
        image_prompt=row["image_prompt"],
        image_path=None,
        status=ContentStatus.PENDING,
    )

    generator = VisualGenerator(pool, client, config)
    dimensions = generator._get_dimensions(str(row["platform"]))
    image_path = await generator._generate_and_save(option, dimensions)
    await generator._update_image_path(id, image_path)

    await client.close()
    logger.info("Regenerated image for option id=%d path=%s", id, image_path)
    return RedirectResponse(url=f"/options/{id}", status_code=302)


# ===================================================================
# Previews
# ===================================================================


@router.get("/preview/{id}", response_class=HTMLResponse)
async def preview_all(request: Request, id: int):
    """Show preview of a content option across all enabled platforms.

    Args:
        request: FastAPI request object.
        id: Content option ID.

    Returns:
        HTML preview page.

    Raises:
        HTTPException 404: If option not found.
    """
    row = await fetch_one(
        """
        SELECT id, batch_id, platform, theme, fact, hashtags,
               image_prompt, image_path, status, created_at, updated_at
        FROM content_options
        WHERE id = $1
        """,
        id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content option not found")

    option = _row_to_dict(row)
    platform = option["platform"]

    config = {
        "PINTEREST_EXTENSION_ID": os.environ.get("PINTEREST_EXTENSION_ID", "PASTE_YOUR_EXTENSION_ID_HERE"),
    }

    return templates.TemplateResponse(
        request,
        f"preview/{platform}.html",
        {
            "option": option,
            "config": config,
        },
    )


@router.get("/preview/{id}/{platform}", response_class=HTMLResponse)
async def preview_platform(request: Request, id: int, platform: str):
    """Show preview for a specific platform.

    Args:
        request: FastAPI request object.
        id: Content option ID.
        platform: Platform name (``"pinterest"`` or ``"instagram"``).

    Returns:
        HTML preview page.

    Raises:
        HTTPException 404: If option not found.
    """
    row = await fetch_one(
        """
        SELECT id, batch_id, platform, theme, fact, hashtags,
               image_prompt, image_path, status, created_at, updated_at
        FROM content_options
        WHERE id = $1 AND platform = $2
        """,
        id,
        platform,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Content option not found")

    option = _row_to_dict(row)

    config = {
        "PINTEREST_EXTENSION_ID": os.environ.get("PINTEREST_EXTENSION_ID", "PASTE_YOUR_EXTENSION_ID_HERE"),
    }

    return templates.TemplateResponse(
        request,
        f"preview/{platform}.html",
        {
            "option": option,
            "config": config,
        },
    )


# ===================================================================
# History
# ===================================================================


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request, platform: str | None = None):
    """List posted content history, optionally filtered by platform.

    Args:
        request: FastAPI request object.
        platform: Optional platform filter.

    Returns:
        HTML history page.
    """
    if platform:
        query = """
            SELECT co.id, co.batch_id, co.platform, co.theme, co.fact,
                   co.hashtags, co.image_path, co.status as content_status,
                   co.created_at, co.updated_at,
                   p.post_url, p.status as post_status
            FROM content_options co
            LEFT JOIN posts p ON p.content_option_id = co.id
            WHERE co.status IN ('posted', 'expired', 'cancelled')
            AND co.platform = $1
            ORDER BY co.created_at DESC
        """
        rows = await fetch(query, platform)
    else:
        query = """
            SELECT co.id, co.batch_id, co.platform, co.theme, co.fact,
                   co.hashtags, co.image_path, co.status as content_status,
                   co.created_at, co.updated_at,
                   p.post_url, p.status as post_status
            FROM content_options co
            LEFT JOIN posts p ON p.content_option_id = co.id
            WHERE co.status IN ('posted', 'expired', 'cancelled')
            ORDER BY co.created_at DESC
        """
        rows = await fetch(query)

    history_items = []
    for r in rows:
        item = _row_to_dict(r)
        item["post_url"] = r.get("post_url")
        item["post_status"] = r.get("post_status")
        item["content_status"] = r.get("content_status")
        history_items.append(item)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "options": [],
            "history_items": history_items,
            "current_platform": platform,
            "history_mode": True,
        },
    )


# ===================================================================
# Content Generation
# ===================================================================


@router.post("/generate", status_code=202)
async def trigger_generation():
    """Trigger the content generation pipeline in the background.

    Returns 202 Accepted if the pipeline was started.
    Returns 409 Conflict if a generation is already running.

    If the state gets stuck in ``running``, use ``POST /generate/reset``
    to reset it back to ``idle``.

    Raises:
        HTTPException 409: If a generation is already in progress.
    """
    from shared.db import get_pool
    from shared.openrouter_client import OpenRouterClient
    from shared.config_loader import load_config
    from app.scheduler import (
        run_pipeline,
        update_generation_state,
        get_generation_state,
    )

    pool = await get_pool()

    # Check if already running
    state = await get_generation_state(pool)
    if state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Generation already in progress",
        )

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    client = OpenRouterClient(api_key)
    config = {
        "content_template": load_config("content_template"),
        "platforms": load_config("platforms"),
        "backup_trends": load_config("backup_trends"),
    }

    await update_generation_state(pool, "running", "Starting generation...")

    async def _run():
        """Background task wrapper that ensures client cleanup."""
        try:
            result = await run_pipeline(pool, client, config)
            logger.info("Manual generation result: %s", result)
        except Exception as exc:
            logger.exception("Manual generation failed")
            try:
                await update_generation_state(
                    pool,
                    "failed",
                    error_message=str(exc),
                    progress_message=f"Failed: {exc}",
                )
            except Exception:
                logger.exception("Failed to update generation state after error")
        finally:
            try:
                await client.close()
            except Exception:
                logger.exception("Failed to close OpenRouter client")

    asyncio.create_task(_run())
    logger.info("Manual generation triggered in background")
    return {"status": "started"}


@router.post("/generate/reset")
async def reset_generation():
    """Reset the generation state back to idle.

    Useful if a pipeline crashes in a way that leaves the state stuck
    in ``running`` (e.g., SIGKILL).  Returns the new idle state.

    Returns:
        JSON with ``status``, ``message``, and ``updated_at`` fields.
    """
    from shared.db import get_pool
    from app.scheduler import reset_generation_state, get_generation_state

    pool = await get_pool()
    await reset_generation_state(pool)
    state = await get_generation_state(pool)
    logger.info("Generation state reset to idle")
    return {
        "status": state["status"],
        "message": state.get("progress_message", ""),
        "updated_at": state.get("updated_at", ""),
    }


@router.get("/generate/status")
async def generation_status():
    """Get the current generation pipeline status.

    Returns:
        JSON with ``status``, ``message``, and ``updated_at`` fields.
    """
    from shared.db import get_pool
    from app.scheduler import get_generation_state

    pool = await get_pool()
    state = await get_generation_state(pool)
    return {
        "status": state["status"],
        "message": state.get("progress_message", ""),
        "error_message": state.get("error_message", ""),
        "updated_at": state.get("updated_at", ""),
    }


@router.websocket("/generate/ws")
async def generation_status_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time generation status updates.

    Polls the generation_state table every 1 second and pushes
    status updates to the client. Closes when status is
    ``completed`` or ``failed``.

    Args:
        websocket: The WebSocket connection.
    """
    await websocket.accept()
    from shared.db import get_pool
    from app.scheduler import get_generation_state

    pool = await get_pool()
    try:
        while True:
            state = await get_generation_state(pool)
            await websocket.send_json({
                "status": state["status"],
                "message": state.get("progress_message", ""),
                "error_message": state.get("error_message", ""),
                "updated_at": state.get("updated_at", ""),
            })
            if state["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


# ===================================================================
# Health Check
# ===================================================================


@router.get("/health")
async def health():
    """Health check endpoint.

    Returns:
        JSON with ``status``, ``database`` (connection test), and ``timestamp``.
    """
    db_ok = False
    try:
        await fetch("SELECT 1")
        db_ok = True
    except Exception:
        logger.warning("Health check — database connection failed")

    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ===================================================================
# Helper
# ===================================================================


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a database row to a dict suitable for template rendering.

    Args:
        row: asyncpg Record (or dict-like).

    Returns:
        Dict with serializable values.
    """
    hashtags_raw = row.get("hashtags")
    if isinstance(hashtags_raw, list):
        hashtags = hashtags_raw
    elif isinstance(hashtags_raw, str):
        import json
        hashtags = json.loads(hashtags_raw)
    else:
        hashtags = []
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "platform": str(row["platform"]) if row.get("platform") else "",
        "theme": row.get("theme", ""),
        "fact": row.get("fact", ""),
        "hashtags": hashtags,
        "hashtag_count": len(hashtags),
        "fact_length": len(row.get("fact", "")),
        "image_prompt": row.get("image_prompt"),
        "image_path": row.get("image_path"),
        "status": row.get("status", ""),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
