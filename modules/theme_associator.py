"""ThemeAssociator module — creates short theme names from trend keywords using AI.

Provides the ThemeAssociator class which:
1. Generates a theme name from a trend keyword via OpenRouter AI
2. Checks deduplication against recently used themes in the database
3. Retries with alternative requests if duplicate is found (max 2 retries)
4. Saves the theme to the themes table
5. Returns the saved Theme model
"""

from __future__ import annotations

import logging
import re
from typing import Any

from shared.models import Theme, Trend

logger = logging.getLogger(__name__)


class ThemeAssociator:
    """Creates short, memorable theme names (max 3 words) from trending keywords.

    Uses OpenRouter AI to associate a trend keyword with a creative theme name,
    then deduplicates against recently used themes before saving.

    Args:
        db_pool: An asyncpg connection pool (or mock with fetch/fetch_one/execute).
        openrouter_client: An OpenRouterClient instance with ``generate_text()``.
        config: The ``content_template.yaml`` config dict. Expected keys:
            ``theme_prompt`` (str with ``{keyword}`` placeholder),
            ``deduplication.min_hours_between_similar`` (int).
    """

    def __init__(self, db_pool: Any, openrouter_client: Any, config: dict[str, Any]) -> None:
        self._db = db_pool
        self._client = openrouter_client
        self._config = config
        self._prompt_template: str = config.get("theme_prompt", "")
        dedup_config = config.get("deduplication", {})
        self._min_hours: int = dedup_config.get("min_hours_between_similar", 12)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, trend: Trend) -> Theme:
        """Create a theme from a trend keyword.

        Process:
        1. Generate theme name from trend keyword via OpenRouter
        2. Check deduplication against recent themes
        3. If duplicate, retry with alternative request (max 2 retries)
        4. Save theme to database
        5. Return saved Theme model

        Args:
            trend: The Trend model to create a theme for.

        Returns:
            The saved Theme model.

        Raises:
            RuntimeError: If theme generation fails after all retries.
        """
        keyword = trend.keyword
        theme_name = ""

        for attempt in range(3):  # Max 2 retries = 3 total attempts
            theme_name = await self._generate_theme(keyword, is_retry=(attempt > 0))
            theme_name = self._clean_theme_name(theme_name)

            if not theme_name:
                logger.warning("Empty theme name received on attempt %d", attempt + 1)
                continue

            if not await self._is_duplicate(theme_name, self._min_hours):
                return await self._save_theme(theme_name, trend.id)

            logger.warning(
                "Theme %r is a duplicate (attempt %d/3); requesting alternative",
                theme_name,
                attempt + 1,
            )

        # All retries exhausted — accept the last generated theme even if duplicate
        logger.warning(
            "All retries exhausted for trend %r; accepting last theme %r",
            keyword,
            theme_name,
        )
        return await self._save_theme(theme_name, trend.id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate_theme(self, keyword: str, is_retry: bool = False) -> str:
        """Call OpenRouter to generate a theme name from a keyword.

        Args:
            keyword: The trend keyword to generate a theme for.
            is_retry: Whether this is a retry (uses alternative prompt).

        Returns:
            The raw theme name string (may need cleaning).

        Raises:
            RuntimeError: If the OpenRouter API call fails after retry.
        """
        if is_retry:
            prompt = (
                f"That theme was used recently. Suggest a different one for '{keyword}'. "
                f"Return ONLY the theme name (up to 3 words), nothing else."
            )
        else:
            prompt = self._prompt_template.format(keyword=keyword)

        logger.info("Generating theme for keyword=%r (retry=%s)", keyword, is_retry)

        try:
            response = await self._client.generate_text(
                prompt=prompt,
                model="openai/gpt-4o-mini",
                max_tokens=50,
                temperature=0.7,
            )
        except Exception:
            logger.exception("OpenRouter API error during theme generation")
            raise

        return response.strip()

    @staticmethod
    def _clean_theme_name(name: str) -> str:
        """Clean and validate a theme name.

        - Strips whitespace
        - Removes surrounding quotes and punctuation
        - Truncates to max 3 words

        Args:
            name: The raw theme name from AI.

        Returns:
            Cleaned theme name.
        """
        name = name.strip().strip("\"'!.?")

        # Split into words and take at most 3
        words = name.split()
        if len(words) > 3:
            logger.warning("Theme %r has %d words; truncating to 3", name, len(words))
            words = words[:3]

        return " ".join(words)

    async def _is_duplicate(self, theme_name: str, hours: int) -> bool:
        """Check if a theme name is too similar to recently used themes.

        Uses ILIKE for case-insensitive fuzzy matching.

        Args:
            theme_name: The theme name to check.
            hours: Lookback window in hours.

        Returns:
            True if a similar theme was found.
        """
        query = """
            SELECT name FROM themes
            WHERE created_at > CURRENT_TIMESTAMP - $1::interval
            AND (
                name ILIKE $2
                OR name ILIKE '%' || $2 || '%'
                OR $2 ILIKE '%' || name || '%'
            )
            LIMIT 1
        """
        row = await self._db.fetch_one(query, f"{hours} hours", theme_name)
        return row is not None

    async def _save_theme(self, name: str, trend_id: int) -> Theme:
        """INSERT a theme into the themes table and return a Theme model.

        Args:
            name: The theme name.
            trend_id: The associated trend ID.

        Returns:
            The saved Theme model with generated id and created_at.

        Raises:
            RuntimeError: If the INSERT returns no row.
        """
        query = """
            INSERT INTO themes (name, trend_id)
            VALUES ($1, $2)
            RETURNING id, name, trend_id, created_at
        """
        row = await self._db.fetch_one(query, name, trend_id)
        if row is None:
            raise RuntimeError("INSERT into themes table returned no row.")

        theme = Theme(
            id=row["id"],
            name=row["name"],
            trend_id=row["trend_id"],
            created_at=row["created_at"],
        )
        logger.info(
            "Saved theme: id=%d name=%r trend_id=%d",
            theme.id,
            theme.name,
            theme.trend_id,
        )
        return theme
