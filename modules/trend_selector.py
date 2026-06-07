"""TrendSelector module — selects trending topics from Google Trends.

Provides the TrendSelector class which:
1. Fetches trending searches from Google Trends RSS feed
2. Filters for food-related keywords using Google Trends' Food & Drink category
3. Deduplicates against recently used keywords in the database
4. Selects the highest-scoring unused keyword
5. Saves it to the trends table
6. Falls back to config-based backup trends when the feed is unavailable
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import httpx

from shared.models import Trend

logger = logging.getLogger(__name__)



class TrendSelector:
    """Selects trending topics from Google Trends.

    The selector fetches real-time trends (using Google Trends' Food & Drink
    category), checks the database for recently used keywords, and picks the
    highest-scoring unused trend.  When the Google Trends API is unavailable,
    it falls back to a list of backup trends defined in
    ``config/backup_trends.yaml``.

    Args:
        db_pool: An asyncpg connection pool used for database queries.
        config: The full ``backup_trends.yaml`` config dictionary (not just the
            ``backup_trends`` key).  Expected keys: ``backup_trends`` (list of
            dicts with ``keyword`` and ``score``), ``trend_history_days`` (int).
    """

    def __init__(self, db_pool: Any, config: dict[str, Any]) -> None:
        self._db = db_pool
        self._config = config
        self._backup_trends: list[dict[str, Any]] = config.get("backup_trends", [])
        self._history_days: int = config.get("trend_history_days", 30)
        self._geo: str = config.get("geo", "US")
        self._period: str = config.get("period", "now 1-d")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> Trend | None:
        """Main execution method.

        Process:
        1. Fetch trending searches via pytrends
        2. Filter for food-related keywords
        3. Query DB for recently used keywords (within *trend_history_days*)
        4. Select highest-scoring unused keyword
        5. Save to the ``trends`` table
        6. Return the saved :class:`Trend` model

        Returns:
            The selected Trend, or ``None`` if no suitable trend was found
            (including when all fallbacks are exhausted).
        """
        candidates = await self._fetch_trends()

        # If the API returned nothing, go straight to backups
        if not candidates:
            logger.warning("No trends returned from API; trying backup trends.")
            return await self._use_backup()

        used = await self._get_used_keywords(self._history_days)
        best = await self._select_best(candidates, used)

        if best is None:
            logger.info("All API trends have been used recently; trying backup trends.")
            return await self._use_backup()

        return await self._save_trend(
            keyword=best["keyword"],
            score=best["score"],
            source="google_trends",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_trends(self) -> list[dict[str, Any]]:
        """Fetch trending searches from Google Trends RSS feed.

        Uses the official Google Trends RSS feed which returns real-time
        daily trending searches. Falls back to backup trends if the feed
        is unavailable.

        Returns:
            List of dicts with ``{"keyword": str, "score": float}``.
        """
        import xml.etree.ElementTree as ET

        url = f"https://trends.google.com/trending/rss?geo={self._geo}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception:
            logger.warning(
                "Google Trends RSS feed request failed; trying backup trends.",
                exc_info=True,
            )
            return []

        try:
            root = ET.fromstring(response.text)
        except Exception:
            logger.warning(
                "Failed to parse Google Trends RSS feed.",
                exc_info=True,
            )
            return []

        ns = {"ht": "https://trends.google.com/trending/rss"}
        items = root.findall(".//item")

        if not items:
            logger.warning("Google Trends RSS feed returned no items.")
            return []

        results: list[dict[str, Any]] = []
        for i, item in enumerate(items):
            title_el = item.find("title")
            if title_el is None or not title_el.text:
                continue
            keyword = title_el.text.strip()
            if not keyword:
                continue

            # Score: 100.0 for top trend, decreasing by 5 per entry
            score = max(100.0 - i * 5, 0.0)
            results.append({"keyword": keyword, "score": score})

        logger.info(
            "Fetched %d trends from Google RSS feed.",
            len(results),
        )
        return results

    async def _get_used_keywords(self, days: int) -> set[str]:
        """Query the ``trends`` table for keywords used in the last *days* days.

        Returns:
            A set of keyword strings.
        """
        query = """
            SELECT DISTINCT keyword
              FROM trends
             WHERE created_at >= CURRENT_TIMESTAMP - $1::interval
        """
        rows = await self._db.fetch(query, timedelta(days=days))
        return {row["keyword"] for row in rows}

    async def _select_best(
        self,
        candidates: list[dict[str, Any]],
        used: set[str],
    ) -> dict[str, Any] | None:
        """Select the highest-scoring unused trend.

        Algorithm:
        1. Filter *candidates* — remove any keyword already in *used*
        2. Sort remaining by ``score`` descending
        3. Pick the first (highest score)
        4. If no unused candidates remain, return ``None``

        Args:
            candidates: List of ``{"keyword": ..., "score": ...}`` dicts.
            used: Set of keyword strings that have been used recently.

        Returns:
            The best candidate dict, or ``None``.
        """
        unused = [c for c in candidates if c["keyword"] not in used]
        if not unused:
            return None
        unused.sort(key=lambda c: c["score"], reverse=True)
        return unused[0]

    async def _save_trend(
        self,
        keyword: str,
        score: float,
        source: str,
    ) -> Trend:
        """INSERT a trend into the ``trends`` table and return a :class:`Trend` model.

        Args:
            keyword: The trending keyword.
            score: The relevance score (0.0 – 100.0).
            source: The source identifier (e.g. ``"google_trends"``).

        Returns:
            The saved Trend model with generated ``id`` and ``created_at``.
        """
        query = """
            INSERT INTO trends (keyword, score, source)
            VALUES ($1, $2, $3)
            RETURNING id, keyword, score, source, created_at
        """
        row = await self._db.fetchrow(query, keyword, score, source)
        if row is None:
            raise RuntimeError("INSERT into trends table returned no row.")

        trend = Trend(
            id=row["id"],
            keyword=row["keyword"],
            score=float(row["score"]),
            source=row["source"],
            created_at=row["created_at"],
        )
        logger.info(
            "Saved trend: id=%d keyword=%r score=%.1f source=%r",
            trend.id,
            trend.keyword,
            trend.score,
            trend.source,
        )
        return trend

    async def _use_backup(self) -> Trend | None:
        """Use a backup trend from config when the API fails.

        Iterates through the ``backup_trends`` list in the config, checks if
        each keyword has been used recently (within *trend_history_days*), and
        saves the first unused one.  If all backup trends have been used,
        returns ``None``.

        Returns:
            The saved Trend model, or ``None`` if all backups are exhausted.
        """
        if not self._backup_trends:
            logger.warning("No backup trends configured.")
            return None

        used = await self._get_used_keywords(self._history_days)

        for entry in self._backup_trends:
            keyword = entry["keyword"]
            if keyword in used:
                logger.info("Backup trend %r already used recently; skipping.", keyword)
                continue

            logger.info("Using backup trend: %r (score=%.1f)", keyword, entry["score"])
            return await self._save_trend(
                keyword=keyword,
                score=entry["score"],
                source="backup",
            )

        logger.error("All backup trends have been used recently.")
        return None



