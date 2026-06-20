"""VisualGenerator module — generates images for content options using AI.

Provides the VisualGenerator class which:
1. Queries content options with image prompts but no images
2. For each option, generates an image via OpenRouter (black-forest-labs/flux.2-klein-4b)
3. Saves images to data/images/ with platform-specific aspect ratios
4. Updates the content_options table with the image path
5. Returns the updated ContentOption models

The model is configured in ``config/platforms.yaml`` under ``visual.model``.
Platform-specific dimensions in ``visual.dimensions`` are used to derive the
aspect ratio passed to the API — the model generates at its native resolution
with the requested aspect ratio, avoiding wasteful post-generation resizing.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any

from shared.models import ContentOption

logger = logging.getLogger(__name__)

# Aspect ratio mapping per platform (for OpenRouter image generation)
ASPECT_RATIO_MAP: dict[str, str] = {
    "pinterest": "2:3",   # portrait
    "instagram": "1:1",   # square
}


class VisualGenerator:
    """Generates images for content options using AI image generation.

    Reads content options that have ``image_prompt`` but no ``image_path``,
    generates images via OpenRouter with platform-specific dimensions,
    saves them to ``data/images/``, and updates the database.

    Args:
        db_pool: An asyncpg connection pool (or mock with fetch/fetch_one/execute).
        openrouter_client: An OpenRouterClient instance with ``generate_image()``.
        config: The ``platforms.yaml`` config dict. Expected keys:
            ``visual.dimensions`` (per-platform width/height),
            ``visual.model`` (default ``"dall-e-3"``),
            ``visual.image_size`` (default ``"0.5K"``).
    """

    def __init__(self, db_pool: Any, openrouter_client: Any, config: dict[str, Any]) -> None:
        self._db = db_pool
        self._client = openrouter_client
        self._config = config

        visual_config = config.get("visual", {})
        self._model: str = visual_config.get("model", "openai/dall-e-3")
        self._image_size: str = visual_config.get("image_size", "0.5K")
        self._dimensions: dict[str, dict[str, int]] = visual_config.get("dimensions", {})
        self._images_dir = "data/images"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, content_option_ids: list[int] | None = None) -> list[ContentOption]:
        """Generate images for content options.

        Process:
        1. Query content_options for options needing image generation
        2. For each option:
           a. Determine platform-specific dimensions
           b. Call OpenRouter image generation
           c. Save image bytes to ``data/images/``
           d. Update content_options.image_path
        3. Return updated ContentOption models

        Args:
            content_option_ids: Specific option IDs to process, or ``None``
                to process all pending options without images.

        Returns:
            List of updated ContentOption models.
        """
        pending = await self._get_pending_options(content_option_ids)
        if not pending:
            logger.info("No pending options to generate images for")
            return []

        # Ensure images directory exists
        os.makedirs(self._images_dir, exist_ok=True)

        updated_options: list[ContentOption] = []
        for option in pending:
            try:
                dimensions = self._get_dimensions(option.platform)
                image_path = await self._generate_and_save(option, dimensions)
                await self._update_image_path(option.id, image_path)
                option.image_path = image_path
                updated_options.append(option)
                logger.info(
                    "Generated image for option id=%d platform=%s path=%s",
                    option.id,
                    option.platform,
                    image_path,
                )
            except Exception:
                logger.exception(
                    "Failed to generate image for option id=%d; skipping",
                    option.id,
                )
                continue

        logger.info(
            "Image generation complete: %d/%d images generated",
            len(updated_options),
            len(pending),
        )
        return updated_options

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_pending_options(
        self, ids: list[int] | None
    ) -> list[ContentOption]:
        """Query for content options needing image generation.

        Args:
            ids: Specific option IDs, or ``None`` for all pending without images.

        Returns:
            List of ContentOption models with ``image_prompt`` but no ``image_path``.
        """
        if ids is not None:
            query = """
                SELECT id, batch_id, platform, theme, fact, hashtags,
                       image_prompt, image_path, status, created_at, updated_at
                FROM content_options
                WHERE id = ANY($1::int[])
                AND image_prompt IS NOT NULL
                AND image_path IS NULL
                AND status = 'pending'
                ORDER BY created_at ASC
            """
            rows = await self._db.fetch(query, list(ids))
        else:
            query = """
                SELECT id, batch_id, platform, theme, fact, hashtags,
                       image_prompt, image_path, status, created_at, updated_at
                FROM content_options
                WHERE image_prompt IS NOT NULL
                AND image_path IS NULL
                AND status = 'pending'
                ORDER BY created_at ASC
            """
            rows = await self._db.fetch(query)

        options: list[ContentOption] = []
        for row in rows:
            option = ContentOption(
                id=row["id"],
                batch_id=row["batch_id"],
                platform=str(row["platform"]),
                theme=row["theme"],
                fact=row["fact"],
                hashtags=list(row["hashtags"]) if row.get("hashtags") else [],
                image_prompt=row.get("image_prompt"),
                image_path=row.get("image_path"),
                status=row["status"],
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
            options.append(option)

        return options

    def _get_dimensions(self, platform: str) -> dict[str, int]:
        """Get image dimensions for a platform.

        Args:
            platform: Platform name (e.g. ``"pinterest"``, ``"instagram"``).

        Returns:
            Dict with ``width`` and ``height`` keys, or default 1024x1024.
        """
        platform_dims = self._dimensions.get(platform, {})
        if platform_dims:
            return {
                "width": platform_dims.get("width", 1024),
                "height": platform_dims.get("height", 1024),
            }
        return {"width": 1024, "height": 1024}

    def _get_aspect_ratio(self, platform: str) -> str:
        """Get aspect ratio string for a platform.

        Derives the ratio from the platform dimensions in config.
        Falls back to the hardcoded ASPECT_RATIO_MAP, then to "1:1".

        Args:
            platform: Platform name.

        Returns:
            Aspect ratio string like "2:3" or "1:1".
        """
        dims = self._dimensions.get(platform)
        if dims:
            if "aspect_ratio" in dims:
                return dims["aspect_ratio"]
            if dims.get("width") and dims.get("height"):
                from math import gcd
                w, h = dims["width"], dims["height"]
                g = gcd(w, h)
                return f"{w // g}:{h // g}"
        return ASPECT_RATIO_MAP.get(platform, "1:1")

    def _get_output_megapixels(self, platform: str) -> float | None:
        """Get output megapixels setting for a platform.

        Args:
            platform: Platform name.

        Returns:
            Float megapixels value if configured and > 0, or ``None``.
        """
        dims = self._dimensions.get(platform, {})
        mp = dims.get("output_megapixels")
        if mp is not None and mp > 0:
            return float(mp)
        return None

    async def _generate_and_save(
        self,
        option: ContentOption,
        dimensions: dict[str, int],
    ) -> str:
        """Generate an image and save it to disk.

        Args:
            option: ContentOption with an ``image_prompt``.
            dimensions: Dict with ``width`` and ``height`` (used to derive aspect
                ratio and also to resize the generated image to exact platform
                dimensions).

        Returns:
            Relative file path (e.g. ``"data/images/batch_xxx_1.png"``).

        Raises:
            RuntimeError: If the image file cannot be written.
        """
        aspect_ratio = self._get_aspect_ratio(option.platform)
        output_megapixels = self._get_output_megapixels(option.platform)

        logger.info(
            "Generating image for option id=%d platform=%s aspect_ratio=%s output_megapixels=%s",
            option.id,
            option.platform,
            aspect_ratio,
            output_megapixels,
        )

        # Generate image via OpenRouter
        image_bytes = await self._client.generate_image(
            prompt=option.image_prompt or "",
            model=self._model,
            aspect_ratio=aspect_ratio,
            size=self._image_size,
            output_megapixels=output_megapixels,
        )

        # Resize to exact platform dimensions
        if dimensions["width"] > 0 and dimensions["height"] > 0:
            try:
                from PIL import Image as PILImage
                import io
                img = PILImage.open(io.BytesIO(image_bytes))
                img = img.resize(
                    (dimensions["width"], dimensions["height"]),
                    PILImage.LANCZOS,
                )
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image_bytes = buf.getvalue()
                logger.info(
                    "Resized image to %dx%d for platform %s",
                    dimensions["width"],
                    dimensions["height"],
                    option.platform,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to resize image for option id=%d, using original: %s",
                    option.id,
                    exc,
                )

        # Build file path
        filename = f"{option.batch_id}_{option.id}.png"
        filepath = os.path.join(self._images_dir, filename)

        # Write to disk
        try:
            with open(filepath, "wb") as f:
                f.write(image_bytes)
        except OSError as exc:
            logger.error("Failed to write image file %s: %s", filepath, exc)
            raise RuntimeError(f"Failed to write image file {filepath}: {exc}") from exc

        logger.info("Saved image to %s (%d bytes)", filepath, len(image_bytes))
        return filename

    async def _update_image_path(self, option_id: int, image_path: str) -> None:
        """Update the ``image_path`` column for a content option.

        Args:
            option_id: The content option ID.
            image_path: The relative image file path.

        Raises:
            RuntimeError: If no row was updated.
        """
        query = """
            UPDATE content_options
            SET image_path = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        """
        result = await self._db.execute(query, image_path, option_id)
        if "UPDATE 0" in result:
            logger.warning("No content option updated for id=%d", option_id)
