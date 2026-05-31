"""ContentGenerator module — generates platform-specific content options from themes.

Provides the ContentGenerator class which:
1. Checks queue size and expires old pending options
2. For each enabled platform, generates N text variations (fact + hashtags) via AI
3. Generates image prompts for each text variation
4. Saves all options to the content_options table
5. Returns the saved ContentOption models
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from shared.models import ContentOption, ContentStatus, Platform

logger = logging.getLogger(__name__)


class ContentGenerator:
    """Generates platform-specific content options from themes.

    For each enabled platform, generates text variations (fact + hashtags)
    constrained to platform limits, then generates image prompts for each
    variation.  Respects queue limits and expires old pending options.

    Args:
        db_pool: An asyncpg connection pool (or mock with fetch/fetch_one/execute).
        openrouter_client: An OpenRouterClient instance with ``generate_text()``.
        config: The ``content_template.yaml`` config dict. Expected keys:
            ``text_prompt``, ``image_prompt``, ``platforms``, ``variations``,
            ``queue.max_pending``, ``queue.expire_days``,
            ``queue.cleanup_on_generate``.
    """

    def __init__(self, db_pool: Any, openrouter_client: Any, config: dict[str, Any]) -> None:
        self._db = db_pool
        self._client = openrouter_client
        self._config = config

        self._text_prompt_template: str = config.get("text_prompt", "")
        self._image_prompt_template: str = config.get("image_prompt", "")
        self._platforms_config: dict[str, Any] = config.get("platforms", {})
        self._variations: int = config.get("variations", 3)

        queue_config = config.get("queue", {})
        self._max_pending: int = queue_config.get("max_pending", 10)
        self._expire_days: int = queue_config.get("expire_days", 7)
        self._cleanup_on_generate: bool = queue_config.get("cleanup_on_generate", True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, theme: Any, platforms: list[str]) -> list[ContentOption]:
        """Generate content options for a theme, for each platform.

        Process:
        1. Check queue size — if >= max_pending, log and return empty list
        2. Expire old pending options (older than expire_days)
        3. For each platform:
           a. Load platform-specific constraints from config
           b. Generate N text variations via OpenRouter
           c. For each text variation, generate image prompt via OpenRouter
           d. Save all options to content_options table
        4. Return combined list of all saved ContentOption models

        Args:
            theme: Theme model (or object with ``.name`` attribute).
            platforms: List of platform names (e.g. ``["pinterest", "instagram"]``).

        Returns:
            List of saved ContentOption models.
        """
        theme_name = theme.name if hasattr(theme, "name") else str(theme)

        # Step 1: Check queue
        queue_size = await self._check_queue()
        if queue_size >= self._max_pending:
            logger.info(
                "Queue full (%d >= %d); skipping content generation",
                queue_size,
                self._max_pending,
            )
            return []

        # Step 2: Expire old options
        if self._cleanup_on_generate:
            expired = await self._expire_old_options(self._expire_days)
            if expired > 0:
                logger.info("Expired %d old pending options", expired)

        # Step 3: Generate for each platform
        batch_id = self._generate_batch_id()
        all_options: list[ContentOption] = []

        for platform_name in platforms:
            if platform_name not in self._platforms_config:
                logger.warning("Platform %r not found in config; skipping", platform_name)
                continue

            platform_limits = self._platforms_config[platform_name]
            logger.info(
                "Generating %d variations for platform=%s theme=%r",
                self._variations,
                platform_name,
                theme_name,
            )

            try:
                text_variations = await self._generate_text_variations(
                    theme=theme_name,
                    count=self._variations,
                    platform_limits=platform_limits,
                )
            except Exception:
                logger.exception(
                    "Text generation failed for platform=%s theme=%r; skipping",
                    platform_name,
                    theme_name,
                )
                continue

            if not text_variations:
                logger.warning(
                    "No text variations generated for platform=%s theme=%r",
                    platform_name,
                    theme_name,
                )
                continue

            # Generate image prompt for each text variation
            platform_options: list[dict[str, Any]] = []
            for variation in text_variations:
                fact = variation.get("fact", "")
                hashtags = variation.get("hashtags", [])

                if not fact:
                    logger.warning("Empty fact in variation; skipping")
                    continue

                try:
                    image_prompt = await self._generate_image_prompt(fact)
                except Exception:
                    logger.exception("Image prompt generation failed for fact; using fallback")
                    image_prompt = f"A food photography image about: {theme_name}"

                platform_options.append({
                    "fact": fact,
                    "hashtags": hashtags,
                    "image_prompt": image_prompt,
                })

            if not platform_options:
                logger.warning(
                    "No valid options for platform=%s theme=%r",
                    platform_name,
                    theme_name,
                )
                continue

            # Save to database
            saved = await self._save_options(
                theme=theme_name,
                batch_id=batch_id,
                platform=platform_name,
                options=platform_options,
            )
            all_options.extend(saved)

            logger.info(
                "Generated %d options for platform=%s theme=%r",
                len(saved),
                platform_name,
                theme_name,
            )

        logger.info(
            "Content generation complete: %d total options for theme=%r",
            len(all_options),
            theme_name,
        )
        return all_options

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    async def _check_queue(self) -> int:
        """Count pending content options in the database.

        Returns:
            Number of options with status ``'pending'``.
        """
        query = "SELECT COUNT(*) FROM content_options WHERE status = 'pending'"
        count = await self._db.fetch_val(query)
        return count or 0

    async def _expire_old_options(self, days: int) -> int:
        """Expire old pending options by setting their status to ``'expired'``.

        Args:
            days: Age in days beyond which options are considered expired.

        Returns:
            Number of options expired.
        """
        query = """
            UPDATE content_options
            SET status = 'expired', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'pending'
            AND created_at < CURRENT_TIMESTAMP - $1::interval
        """
        result = await self._db.execute(query, f"{days} days")
        # Extract count from result string like "UPDATE 5"
        match = re.search(r"UPDATE\s+(\d+)", result)
        return int(match.group(1)) if match else 0

    # ------------------------------------------------------------------
    # AI generation helpers
    # ------------------------------------------------------------------

    async def _generate_text_variations(
        self,
        theme: str,
        count: int,
        platform_limits: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate N text variations (fact + hashtags) for a theme.

        Calls OpenRouter with the text prompt template formatted with the
        theme and platform constraints appended.  Expects JSON response.

        Args:
            theme: Theme name.
            count: Number of variations to generate.
            platform_limits: Dict with ``character_limit`` and ``hashtag_count``.

        Returns:
            List of dicts with ``{"fact": str, "hashtags": list[str]}``.
        """
        char_limit = platform_limits.get("character_limit", 500)
        hashtag_range = platform_limits.get("hashtag_count", "5-10")

        prompt = (
            self._text_prompt_template.format(theme=theme)
            + f"\n\nPlatform constraints: character limit {char_limit}, "
            f"hashtag count {hashtag_range}."
            f"\n\nGenerate {count} different variations. "
            f"Return a JSON array: [{{\"fact\": \"...\", \"hashtags\": [\"...\", \"...\"]}}, ...]"
        )

        logger.info(
            "Generating %d text variations for theme=%r (char_limit=%d)",
            count,
            theme,
            char_limit,
        )

        try:
            response = await self._client.generate_text(
                prompt=prompt,
                model="openai/gpt-4o-mini",
                max_tokens=2000,
                temperature=0.8,
                response_format={"type": "json_object"},
            )
        except Exception:
            logger.exception("OpenRouter API error during text generation")
            raise

        return self._parse_text_variations(response, count)

    def _parse_text_variations(
        self, response: str, expected_count: int
    ) -> list[dict[str, Any]]:
        """Parse the JSON response from OpenRouter into text variations.

        Attempts to parse as JSON array first, then as JSON object with a
        ``variations`` key.  Falls back to regex extraction if JSON parsing
        fails.

        Args:
            response: Raw response string from OpenRouter.
            expected_count: Expected number of variations.

        Returns:
            List of dicts with ``{"fact": str, "hashtags": list[str]}``.
        """
        # Try parsing as JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON response; attempting regex fallback")
            return self._parse_text_variations_regex(response)

        # Handle both array and object formats
        if isinstance(data, list):
            variations = data
        elif isinstance(data, dict):
            variations = data.get("variations", data.get("options", [data]))
            if isinstance(variations, dict):
                variations = [variations]
        else:
            logger.warning("Unexpected JSON structure; attempting regex fallback")
            return self._parse_text_variations_regex(response)

        result: list[dict[str, Any]] = []
        for var in variations:
            if isinstance(var, dict):
                fact = var.get("fact", "")
                hashtags = var.get("hashtags", [])
                if isinstance(hashtags, str):
                    hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]
                if not isinstance(hashtags, list):
                    hashtags = []
                # Ensure hashtags have # prefix
                hashtags = [
                    h if h.startswith("#") else f"#{h}" for h in hashtags
                ]
                if fact:
                    result.append({"fact": fact, "hashtags": hashtags})

        if len(result) < expected_count:
            logger.warning(
                "Expected %d variations but got %d",
                expected_count,
                len(result),
            )

        return result

    @staticmethod
    def _parse_text_variations_regex(response: str) -> list[dict[str, Any]]:
        """Fallback parser using regex to extract fact and hashtags.

        Args:
            response: Raw response string.

        Returns:
            List of dicts with ``{"fact": str, "hashtags": list[str]}``.
        """
        variations: list[dict[str, Any]] = []

        # Try to find fact/hashtags pairs
        fact_pattern = re.compile(r'"fact"\s*:\s*"([^"]+)"', re.IGNORECASE)
        hashtag_pattern = re.compile(r'"hashtags"\s*:\s*\[([^\]]*)\]', re.IGNORECASE)

        facts = fact_pattern.findall(response)
        hashtag_matches = hashtag_pattern.findall(response)

        for i, fact in enumerate(facts):
            hashtags: list[str] = []
            if i < len(hashtag_matches):
                raw = hashtag_matches[i]
                hashtags = re.findall(r'"([^"]+)"', raw)
                hashtags = [
                    h if h.startswith("#") else f"#{h}" for h in hashtags
                ]
            variations.append({"fact": fact, "hashtags": hashtags})

        return variations

    async def _generate_image_prompt(self, fact: str) -> str:
        """Generate an image prompt from a fact using OpenRouter.

        Args:
            fact: The fact text to base the image on.

        Returns:
            Image description string (2-3 sentences).
        """
        prompt = self._image_prompt_template.format(fact=fact)

        logger.info("Generating image prompt for fact (len=%d)", len(fact))

        try:
            response = await self._client.generate_text(
                prompt=prompt,
                model="openai/gpt-4o-mini",
                max_tokens=300,
                temperature=0.7,
            )
        except Exception:
            logger.exception("OpenRouter API error during image prompt generation")
            raise

        return response.strip()

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------

    async def _save_options(
        self,
        theme: str,
        batch_id: str,
        platform: str,
        options: list[dict[str, Any]],
    ) -> list[ContentOption]:
        """Batch INSERT content options into the database.

        Args:
            theme: Theme name.
            batch_id: Unique batch identifier.
            platform: Target platform name.
            options: List of dicts with ``fact``, ``hashtags``, ``image_prompt``.

        Returns:
            List of saved ContentOption models.

        Raises:
            RuntimeError: If the INSERT returns no rows.
        """
        query = """
            INSERT INTO content_options (batch_id, platform, theme, fact, hashtags, image_prompt, status, created_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, 'pending', CURRENT_TIMESTAMP)
            RETURNING id, batch_id, platform, theme, fact, hashtags, image_prompt, image_path, status, created_at, updated_at
        """

        saved_options: list[ContentOption] = []
        for opt in options:
            import json as json_module
            hashtags_json = json_module.dumps(opt["hashtags"])
            row = await self._db.fetch_one(
                query,
                batch_id,
                platform,
                theme,
                opt["fact"],
                hashtags_json,
                opt["image_prompt"],
            )
            if row is None:
                raise RuntimeError("INSERT into content_options table returned no row.")

            option = ContentOption(
                id=row["id"],
                batch_id=row["batch_id"],
                platform=row["platform"],
                theme=row["theme"],
                fact=row["fact"],
                hashtags=list(row["hashtags"]) if row.get("hashtags") else [],
                image_prompt=row.get("image_prompt"),
                image_path=row.get("image_path"),
                status=row["status"],
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )
            saved_options.append(option)

        logger.info(
            "Saved %d options to content_options (batch=%s, platform=%s)",
            len(saved_options),
            batch_id,
            platform,
        )
        return saved_options

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_batch_id() -> str:
        """Generate a unique batch identifier.

        Format: ``batch_YYYYMMDD_HHMMSS_xxxxxx``
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_id = uuid.uuid4().hex[:6]
        return f"batch_{timestamp}_{short_id}"
