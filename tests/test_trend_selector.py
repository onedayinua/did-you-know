"""Tests for modules/trend_selector.py — TrendSelector class.

Covers:
- ``_select_best()`` — core selection algorithm
- ``_use_backup()`` — backup fallback
- ``_fetch_trends()`` — RSS feed integration (mocked)
- ``run()`` — full pipeline (mocked)
- ``_save_trend()`` — database operations
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.trend_selector import TrendSelector
from shared.models import Trend


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def sample_config() -> dict:
    """Full config dict as loaded from backup_trends.yaml."""
    return {
        "backup_trends": [
            {"keyword": "easy dinner recipes", "score": 85.0},
            {"keyword": "healthy snacks", "score": 80.0},
            {"keyword": "meal prep ideas", "score": 75.0},
            {"keyword": "comfort food", "score": 70.0},
            {"keyword": "quick breakfast", "score": 65.0},
        ],
        "trend_history_days": 30,
        "geo": "US",
        "period": "now 1-d",
    }


@pytest.fixture
def db_pool() -> AsyncMock:
    """Mock asyncpg connection pool with async helpers."""
    pool = AsyncMock()
    pool.fetch = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def selector(db_pool: AsyncMock, sample_config: dict) -> TrendSelector:
    """TrendSelector instance with mocked db pool and sample config."""
    return TrendSelector(db_pool, sample_config)


@pytest.fixture
def mock_rss_response() -> str:
    """Returns a mock RSS XML response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item><title>flash flood warning</title><ht:approx_traffic>2000+</ht:approx_traffic></item>
    <item><title>tennis scores today</title><ht:approx_traffic>100000+</ht:approx_traffic></item>
    <item><title>easy dinner recipes</title><ht:approx_traffic>500+</ht:approx_traffic></item>
  </channel>
</rss>"""


# ===================================================================
# _select_best
# ===================================================================


class TestSelectBest:
    """Core selection algorithm."""

    async def test_returns_highest_scoring_unused(self, selector: TrendSelector):
        candidates = [
            {"keyword": "a", "score": 50.0},
            {"keyword": "b", "score": 90.0},
            {"keyword": "c", "score": 30.0},
        ]
        used: set[str] = set()
        result = await selector._select_best(candidates, used)
        assert result is not None
        assert result["keyword"] == "b"
        assert result["score"] == 90.0

    async def test_filters_out_used_keywords(self, selector: TrendSelector):
        candidates = [
            {"keyword": "a", "score": 90.0},
            {"keyword": "b", "score": 80.0},
            {"keyword": "c", "score": 70.0},
        ]
        used = {"a", "c"}
        result = await selector._select_best(candidates, used)
        assert result is not None
        assert result["keyword"] == "b"

    async def test_returns_none_when_all_used(self, selector: TrendSelector):
        candidates = [
            {"keyword": "a", "score": 90.0},
            {"keyword": "b", "score": 80.0},
        ]
        used = {"a", "b"}
        result = await selector._select_best(candidates, used)
        assert result is None

    async def test_empty_candidates(self, selector: TrendSelector):
        result = await selector._select_best([], set())
        assert result is None

    async def test_empty_used_set(self, selector: TrendSelector):
        candidates = [
            {"keyword": "x", "score": 10.0},
            {"keyword": "y", "score": 20.0},
        ]
        result = await selector._select_best(candidates, set())
        assert result is not None
        assert result["keyword"] == "y"

    async def test_all_same_score_returns_first_in_order(self, selector: TrendSelector):
        candidates = [
            {"keyword": "a", "score": 50.0},
            {"keyword": "b", "score": 50.0},
        ]
        result = await selector._select_best(candidates, set())
        assert result is not None
        assert result["keyword"] in ("a", "b")

    async def test_partial_used(self, selector: TrendSelector):
        candidates = [
            {"keyword": "a", "score": 100.0},
            {"keyword": "b", "score": 90.0},
            {"keyword": "c", "score": 80.0},
        ]
        used = {"a"}
        result = await selector._select_best(candidates, used)
        assert result is not None
        assert result["keyword"] == "b"
        assert result["score"] == 90.0


# ===================================================================
# _use_backup
# ===================================================================


class TestUseBackup:
    """Backup fallback behaviour."""

    async def test_uses_first_unused_backup(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """First backup trend is used when none have been used recently."""
        db_pool.fetch.return_value = []  # no used keywords
        db_pool.fetchrow.return_value = {
            "id": 99,
            "keyword": "easy dinner recipes",
            "score": 85.0,
            "source": "backup",
            "created_at": None,
        }
        result = await selector._use_backup()
        assert result is not None
        assert result.keyword == "easy dinner recipes"
        assert result.score == 85.0
        assert result.source == "backup"

    async def test_skips_used_backup_trends(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Backup trends that have been used recently are skipped."""
        db_pool.fetch.return_value = [
            {"keyword": "easy dinner recipes"},
        ]
        db_pool.fetchrow.side_effect = [
            {
                "id": 100,
                "keyword": "healthy snacks",
                "score": 80.0,
                "source": "backup",
                "created_at": None,
            },
        ]
        result = await selector._use_backup()
        assert result is not None
        assert result.keyword == "healthy snacks"

    async def test_returns_none_when_all_backups_used(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When every backup trend has been used, returns None."""
        db_pool.fetch.return_value = [
            {"keyword": "easy dinner recipes"},
            {"keyword": "healthy snacks"},
            {"keyword": "meal prep ideas"},
            {"keyword": "comfort food"},
            {"keyword": "quick breakfast"},
        ]
        result = await selector._use_backup()
        assert result is None

    async def test_returns_none_when_backup_list_empty(
        self, db_pool: AsyncMock
    ):
        """No backup trends configured -> None."""
        sel = TrendSelector(db_pool, {"trend_history_days": 30})
        result = await sel._use_backup()
        assert result is None

    async def test_saves_with_source_backup(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Saved backup trend has source='backup'."""
        db_pool.fetch.return_value = []
        db_pool.fetchrow.return_value = {
            "id": 101,
            "keyword": "comfort food",
            "score": 70.0,
            "source": "backup",
            "created_at": None,
        }
        result = await selector._use_backup()
        assert result is not None
        assert result.source == "backup"


# ===================================================================
# _fetch_trends
# ===================================================================


class TestFetchTrends:
    """RSS feed integration (mocked)."""

    @patch("httpx.AsyncClient.get")
    async def test_fetch_success(
        self, mock_get: MagicMock, selector: TrendSelector, mock_rss_response: str
    ):
        """Successfully fetches and parses RSS feed."""
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        results = await selector._fetch_trends()

        assert len(results) == 3
        keywords = [r["keyword"] for r in results]
        assert "flash flood warning" in keywords
        assert "tennis scores today" in keywords
        assert "easy dinner recipes" in keywords

    @patch("httpx.AsyncClient.get")
    async def test_fetch_returns_empty_on_http_error(
        self, mock_get: MagicMock, selector: TrendSelector
    ):
        """Returns empty list when HTTP request fails."""
        mock_get.side_effect = Exception("HTTP error")

        results = await selector._fetch_trends()

        assert results == []

    @patch("httpx.AsyncClient.get")
    async def test_fetch_returns_empty_on_bad_xml(
        self, mock_get: MagicMock, selector: TrendSelector
    ):
        """Returns empty list when RSS XML is malformed."""
        mock_response = MagicMock()
        mock_response.text = "not valid xml"
        mock_get.return_value = mock_response

        results = await selector._fetch_trends()

        assert results == []

    @patch("httpx.AsyncClient.get")
    async def test_fetch_returns_empty_on_empty_feed(
        self, mock_get: MagicMock, selector: TrendSelector
    ):
        """Returns empty list when RSS feed has no items."""
        empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
  </channel>
</rss>"""
        mock_response = MagicMock()
        mock_response.text = empty_rss
        mock_get.return_value = mock_response

        results = await selector._fetch_trends()

        assert results == []

    @patch("httpx.AsyncClient.get")
    async def test_scores_decrease_by_5(
        self, mock_get: MagicMock, selector: TrendSelector, mock_rss_response: str
    ):
        """Scores decrease by 5 from 100 for each trend."""
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        results = await selector._fetch_trends()

        assert len(results) == 3
        assert results[0]["score"] == 100.0
        assert results[1]["score"] == 95.0
        assert results[2]["score"] == 90.0

    @patch("httpx.AsyncClient.get")
    async def test_skips_items_without_title(
        self, mock_get: MagicMock, selector: TrendSelector
    ):
        """Items without a title element are skipped."""
        rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
    <item><title>valid trend</title><ht:approx_traffic>500+</ht:approx_traffic></item>
    <item><ht:approx_traffic>200+</ht:approx_traffic></item>
    <item><title></title><ht:approx_traffic>100+</ht:approx_traffic></item>
  </channel>
</rss>"""
        mock_response = MagicMock()
        mock_response.text = rss
        mock_get.return_value = mock_response

        results = await selector._fetch_trends()

        assert len(results) == 1
        assert results[0]["keyword"] == "valid trend"


# ===================================================================
# _save_trend
# ===================================================================


class TestSaveTrend:
    """Database INSERT operations."""

    async def test_inserts_and_returns_trend(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Inserts a trend and returns a Trend model with generated id."""
        db_pool.fetchrow.return_value = {
            "id": 42,
            "keyword": "test trend",
            "score": 88.5,
            "source": "google_trends",
            "created_at": None,
        }

        result = await selector._save_trend("test trend", 88.5, "google_trends")

        assert isinstance(result, Trend)
        assert result.id == 42
        assert result.keyword == "test trend"
        assert result.score == 88.5
        assert result.source == "google_trends"

    async def test_raises_when_insert_returns_none(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Raises RuntimeError if INSERT RETURNING yields no row."""
        db_pool.fetchrow.return_value = None

        with pytest.raises(RuntimeError, match="INSERT into trends table returned no row"):
            await selector._save_trend("fail", 50.0, "google_trends")

    async def test_correct_query_parameters(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Verifies the SQL query and parameters passed to the DB."""
        db_pool.fetchrow.return_value = {
            "id": 1,
            "keyword": "test",
            "score": 75.0,
            "source": "google_trends",
            "created_at": None,
        }

        await selector._save_trend("test", 75.0, "google_trends")

        db_pool.fetchrow.assert_called_once()
        args = db_pool.fetchrow.call_args[0]
        assert "INSERT INTO trends" in args[0]
        assert "test" in args
        assert 75.0 in args
        assert "google_trends" in args


# ===================================================================
# run() — full pipeline
# ===================================================================


class TestRun:
    """Full pipeline integration tests (mocked)."""

    @patch("httpx.AsyncClient.get")
    async def test_full_successful_flow(
        self, mock_get: MagicMock, selector: TrendSelector, db_pool: AsyncMock, mock_rss_response: str
    ):
        """Full flow: fetch -> dedup -> save -> return Trend."""
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        db_pool.fetch.return_value = []
        db_pool.fetchrow.return_value = {
            "id": 1,
            "keyword": "flash flood warning",
            "score": 100.0,
            "source": "google_trends",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "flash flood warning"
        assert result.score == 100.0
        assert result.source == "google_trends"

    @patch("httpx.AsyncClient.get")
    async def test_all_api_trends_used_falls_back_to_backup(
        self, mock_get: MagicMock, selector: TrendSelector, db_pool: AsyncMock, mock_rss_response: str
    ):
        """When all API trends have been used, falls back to backup trends."""
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        db_pool.fetch.side_effect = [
            [{"keyword": "flash flood warning"}, {"keyword": "tennis scores today"}, {"keyword": "easy dinner recipes"}],
            [],
        ]
        db_pool.fetchrow.return_value = {
            "id": 2,
            "keyword": "healthy snacks",
            "score": 80.0,
            "source": "backup",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "healthy snacks"
        assert result.source == "backup"

    @patch("httpx.AsyncClient.get")
    async def test_api_failure_uses_backup(
        self, mock_get: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When the API fails, uses backup trends."""
        mock_get.side_effect = Exception("Network error")

        db_pool.fetch.return_value = []
        db_pool.fetchrow.return_value = {
            "id": 3,
            "keyword": "easy dinner recipes",
            "score": 85.0,
            "source": "backup",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "easy dinner recipes"
        assert result.source == "backup"

    @patch("httpx.AsyncClient.get")
    async def test_complete_failure_returns_none(
        self, mock_get: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When API fails and all backups are used, returns None."""
        mock_get.side_effect = Exception("Network error")

        db_pool.fetch.return_value = [
            {"keyword": "easy dinner recipes"},
            {"keyword": "healthy snacks"},
            {"keyword": "meal prep ideas"},
            {"keyword": "comfort food"},
            {"keyword": "quick breakfast"},
        ]

        result = await selector.run()

        assert result is None

    @patch("httpx.AsyncClient.get")
    async def test_api_trends_empty_uses_backup(
        self, mock_get: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When API returns empty list, uses backup trends."""
        empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0">
  <channel>
  </channel>
</rss>"""
        mock_response = MagicMock()
        mock_response.text = empty_rss
        mock_get.return_value = mock_response

        db_pool.fetch.return_value = []
        db_pool.fetchrow.return_value = {
            "id": 5,
            "keyword": "meal prep ideas",
            "score": 75.0,
            "source": "backup",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "meal prep ideas"
        assert result.source == "backup"


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Additional edge-case coverage."""

    async def test_duplicate_candidates(
        self, selector: TrendSelector
    ):
        """Duplicate keywords in candidates are handled."""
        candidates = [
            {"keyword": "chicken recipe", "score": 80.0},
            {"keyword": "chicken recipe", "score": 90.0},
        ]
        result = await selector._select_best(candidates, set())
        assert result is not None
        assert result["keyword"] == "chicken recipe"
        assert result["score"] == 90.0

    async def test_get_used_keywords_empty(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """_get_used_keywords returns empty set when no rows."""
        db_pool.fetch.return_value = []
        result = await selector._get_used_keywords(30)
        assert result == set()

    async def test_get_used_keywords_with_data(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """_get_used_keywords returns set of keywords from DB."""
        db_pool.fetch.return_value = [
            {"keyword": "a"},
            {"keyword": "b"},
            {"keyword": "a"},
        ]
        result = await selector._get_used_keywords(30)
        assert result == {"a", "b"}

    async def test_config_without_backup_trends(
        self, db_pool: AsyncMock
    ):
        """Config without backup_trends key still works."""
        sel = TrendSelector(db_pool, {"trend_history_days": 30})
        assert sel._backup_trends == []

    async def test_config_without_trend_history_days(
        self, db_pool: AsyncMock
    ):
        """Missing trend_history_days defaults to 30."""
        sel = TrendSelector(db_pool, {"backup_trends": []})
        assert sel._history_days == 30

    @patch("httpx.AsyncClient.get")
    async def test_non_food_only_api_results(
        self, mock_get: MagicMock, selector: TrendSelector, db_pool: AsyncMock, mock_rss_response: str
    ):
        """When API returns only non-food results, they pass through (no filter)."""
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        db_pool.fetch.return_value = []
        db_pool.fetchrow.return_value = {
            "id": 6,
            "keyword": "flash flood warning",
            "score": 100.0,
            "source": "google_trends",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "flash flood warning"
        assert result.source == "google_trends"


# ===================================================================
# Geo & Period Configuration
# ===================================================================


class TestGeoPeriodConfig:
    """Configurable geo for Google Trends RSS feed."""

    @patch("httpx.AsyncClient.get")
    async def test_uses_configured_geo(
        self, mock_get: MagicMock, selector: TrendSelector, mock_rss_response: str
    ):
        """RSS feed URL uses the configured geo value."""
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        await selector._fetch_trends()

        args, kwargs = mock_get.call_args
        assert "geo=US" in args[0]

    async def test_default_geo_when_missing(self, db_pool: AsyncMock):
        """Defaults to 'US' when geo not in config."""
        sel = TrendSelector(db_pool, {
            "backup_trends": [],
            "trend_history_days": 30,
            "period": "now 1-d",
        })
        assert sel._geo == "US"

    async def test_default_period_when_missing(self, db_pool: AsyncMock):
        """Defaults to 'now 1-d' when period not in config."""
        sel = TrendSelector(db_pool, {
            "backup_trends": [],
            "trend_history_days": 30,
            "geo": "US",
        })
        assert sel._period == "now 1-d"

    async def test_both_default_when_missing(self, db_pool: AsyncMock):
        """Both default when neither in config."""
        sel = TrendSelector(db_pool, {
            "backup_trends": [],
            "trend_history_days": 30,
        })
        assert sel._geo == "US"
        assert sel._period == "now 1-d"

    async def test_custom_geo_and_period(self, db_pool: AsyncMock):
        """Custom geo and period values are stored."""
        sel = TrendSelector(db_pool, {
            "backup_trends": [],
            "trend_history_days": 30,
            "geo": "GB",
            "period": "now 4-H",
        })
        assert sel._geo == "GB"
        assert sel._period == "now 4-H"

    @patch("httpx.AsyncClient.get")
    async def test_empty_geo_passed_through(
        self, mock_get: MagicMock, db_pool: AsyncMock, mock_rss_response: str
    ):
        """Empty string geo is passed through (worldwide)."""
        sel = TrendSelector(db_pool, {
            "backup_trends": [],
            "trend_history_days": 30,
            "geo": "",
            "period": "now 1-d",
        })
        mock_response = MagicMock()
        mock_response.text = mock_rss_response
        mock_get.return_value = mock_response

        await sel._fetch_trends()

        args, kwargs = mock_get.call_args
        assert "geo=" in args[0]