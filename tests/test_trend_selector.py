"""Tests for modules/trend_selector.py — TrendSelector class.

Covers:
- ``_select_best()`` — core selection algorithm
- ``_use_backup()`` — backup fallback
- ``_fetch_trends()`` — pytrends integration (mocked)
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
    pool.fetch_one = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def selector(db_pool: AsyncMock, sample_config: dict) -> TrendSelector:
    """TrendSelector instance with mocked db pool and sample config."""
    return TrendSelector(db_pool, sample_config)


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
        # Both have same score, but after sorting the first is arbitrary;
        # just verify one is returned.
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
        db_pool.fetch_one.return_value = {
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
        # Simulate the DB returning the saved trend
        db_pool.fetch_one.side_effect = [
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
        # "easy dinner recipes" was used, so it should pick "healthy snacks"
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
        db_pool.fetch_one.return_value = {
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
    """pytrends integration (mocked)."""

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_fetch_success(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Successfully fetches and parses trending searches."""
        import pandas as pd

        mock_df = pd.DataFrame(
            {0: ["chicken recipes", "python programming", "healthy dinner ideas"]}
        )

        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = mock_df

        results = await selector._fetch_trends()

        # No longer filtered — all keywords pass through
        assert len(results) == 3
        keywords = [r["keyword"] for r in results]
        assert "chicken recipes" in keywords
        assert "healthy dinner ideas" in keywords
        assert "python programming" in keywords

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_fetch_returns_empty_on_api_failure(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Returns empty list when trending_searches() raises."""
        instance = mock_trend_req.return_value
        instance.trending_searches.side_effect = Exception("API error")

        # Also make realtime_trending_searches fail
        instance.realtime_trending_searches.side_effect = Exception("Realtime error")

        results = await selector._fetch_trends()

        assert results == []

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_fall_through_to_realtime(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Falls through to realtime_trending_searches when trending_searches fails."""
        instance = mock_trend_req.return_value
        instance.trending_searches.side_effect = Exception("Trending error")

        # Realtime returns data
        instance.realtime_trending_searches.return_value = {
            "entries": [
                {"title": "easy pasta dinner"},
                {"title": "latest gadgets"},
                {"title": "homemade pizza"},
            ]
        }

        results = await selector._fetch_trends()

        assert len(results) == 3
        keywords = [r["keyword"] for r in results]
        assert "easy pasta dinner" in keywords
        assert "homemade pizza" in keywords
        assert "latest gadgets" in keywords

    @patch("modules.trend_selector.HAS_PYTRENDS", False)
    async def test_returns_empty_when_pytrends_not_installed(
        self, selector: TrendSelector
    ):
        """When pytrends is not installed, returns empty list."""
        results = await selector._fetch_trends()
        assert results == []

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_realtime_returns_empty_dict(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Handles realtime returning an empty dict gracefully."""
        instance = mock_trend_req.return_value
        instance.trending_searches.side_effect = Exception("Error")
        instance.realtime_trending_searches.return_value = {}

        results = await selector._fetch_trends()

        assert results == []

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_trending_searches_empty_dataframe(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Handles empty DataFrame from trending_searches()."""
        import pandas as pd

        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = pd.DataFrame()

        results = await selector._fetch_trends()

        assert results == []


# ===================================================================
# _save_trend
# ===================================================================


class TestSaveTrend:
    """Database INSERT operations."""

    async def test_inserts_and_returns_trend(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Inserts a trend and returns a Trend model with generated id."""
        db_pool.fetch_one.return_value = {
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
        db_pool.fetch_one.return_value = None

        with pytest.raises(RuntimeError, match="INSERT into trends table returned no row"):
            await selector._save_trend("fail", 50.0, "google_trends")

    async def test_correct_query_parameters(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Verifies the SQL query and parameters passed to the DB."""
        db_pool.fetch_one.return_value = {
            "id": 1,
            "keyword": "test",
            "score": 75.0,
            "source": "google_trends",
            "created_at": None,
        }

        await selector._save_trend("test", 75.0, "google_trends")

        db_pool.fetch_one.assert_called_once()
        args = db_pool.fetch_one.call_args[0]
        assert "INSERT INTO trends" in args[0]
        assert "test" in args
        assert 75.0 in args
        assert "google_trends" in args


# ===================================================================
# run() — full pipeline
# ===================================================================


class TestRun:
    """Full pipeline integration tests (mocked)."""

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_full_successful_flow(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """Full flow: fetch -> dedup -> save -> return Trend."""
        import pandas as pd

        mock_df = pd.DataFrame({0: ["easy dinner recipes", "tech news"]})

        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = mock_df

        # No recently used keywords
        db_pool.fetch.return_value = []
        db_pool.fetch_one.return_value = {
            "id": 1,
            "keyword": "easy dinner recipes",
            "score": 100.0,
            "source": "google_trends",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "easy dinner recipes"
        assert result.score == 100.0
        assert result.source == "google_trends"

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_all_api_trends_used_falls_back_to_backup(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When all API trends have been used, falls back to backup trends."""
        import pandas as pd

        mock_df = pd.DataFrame({0: ["easy dinner recipes"]})

        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = mock_df

        # "easy dinner recipes" was used recently
        db_pool.fetch.side_effect = [
            [{"keyword": "easy dinner recipes"}],   # _get_used_keywords for API
            [],                                      # _get_used_keywords for backup
        ]
        db_pool.fetch_one.return_value = {
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

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_api_failure_uses_backup(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When the API fails, uses backup trends."""
        instance = mock_trend_req.return_value
        instance.trending_searches.side_effect = Exception("Network error")
        instance.realtime_trending_searches.side_effect = Exception("Realtime error")

        # No used keywords for backup
        db_pool.fetch.return_value = []
        db_pool.fetch_one.return_value = {
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

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_complete_failure_returns_none(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When API fails and all backups are used, returns None."""
        instance = mock_trend_req.return_value
        instance.trending_searches.side_effect = Exception("Network error")
        instance.realtime_trending_searches.side_effect = Exception("Realtime error")

        # All backup trends have been used
        db_pool.fetch.return_value = [
            {"keyword": "easy dinner recipes"},
            {"keyword": "healthy snacks"},
            {"keyword": "meal prep ideas"},
            {"keyword": "comfort food"},
            {"keyword": "quick breakfast"},
        ]

        result = await selector.run()

        assert result is None

    @patch("modules.trend_selector.HAS_PYTRENDS", False)
    async def test_pytrends_not_installed_uses_backup(
        self, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When pytrends is not installed, uses backup trends."""
        db_pool.fetch.return_value = []
        db_pool.fetch_one.return_value = {
            "id": 4,
            "keyword": "easy dinner recipes",
            "score": 85.0,
            "source": "backup",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        assert result.keyword == "easy dinner recipes"
        assert result.source == "backup"

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_api_trends_empty_uses_backup(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When API returns empty list, uses backup trends."""
        import pandas as pd

        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = pd.DataFrame()

        db_pool.fetch.return_value = []
        db_pool.fetch_one.return_value = {
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
            {"keyword": "a"},  # duplicate in DB
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

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_non_food_only_api_results(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """When API returns only non-food results, they pass through (no filter)."""
        import pandas as pd

        mock_df = pd.DataFrame({0: ["python programming", "gaming", "technology"]})

        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = mock_df

        # No recently used keywords
        db_pool.fetch.return_value = []
        db_pool.fetch_one.return_value = {
            "id": 6,
            "keyword": "python programming",
            "score": 100.0,
            "source": "google_trends",
            "created_at": None,
        }

        result = await selector.run()

        assert result is not None
        # "python programming" has the highest score (100.0), so it's selected
        assert result.keyword == "python programming"
        assert result.source == "google_trends"


# ===================================================================
# _parse_trending_searches / _parse_realtime_trending
# ===================================================================


class TestParseTrendingSearches:
    """Unit tests for the parsing methods."""

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    def test_parse_trending_scores_decrease(self):
        """Scores decrease by 5 from 100 for each trend."""
        import pandas as pd

        mock_df = pd.DataFrame({0: ["chicken recipe", "pasta dinner", "healthy snacks"]})

        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.return_value = mock_df

        results = TrendSelector._parse_trending_searches(mock_pytrends)

        assert len(results) == 3
        assert results[0]["score"] == 100.0
        assert results[1]["score"] == 95.0
        assert results[2]["score"] == 90.0

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    def test_parse_realtime_extracts_keywords(self):
        """Extracts keywords from realtime trending entries."""
        mock_pytrends = MagicMock()
        mock_pytrends.realtime_trending_searches.return_value = {
            "entries": [
                {"title": "easy chicken dinner"},
                {"title": "world news update"},
                {"title": "homemade pizza recipe"},
            ]
        }

        results = TrendSelector._parse_realtime_trending(mock_pytrends)

        assert len(results) == 3
        keywords = [r["keyword"] for r in results]
        assert "easy chicken dinner" in keywords
        assert "homemade pizza recipe" in keywords
        assert "world news update" in keywords

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    def test_parse_realtime_empty_entries(self):
        """Empty entries list returns empty list."""
        mock_pytrends = MagicMock()
        mock_pytrends.realtime_trending_searches.return_value = {"entries": []}

        results = TrendSelector._parse_realtime_trending(mock_pytrends)
        assert results == []

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    def test_parse_realtime_empty_dict(self):
        """Empty dict returns empty list."""
        mock_pytrends = MagicMock()
        mock_pytrends.realtime_trending_searches.return_value = {}

        results = TrendSelector._parse_realtime_trending(mock_pytrends)
        assert results == []


# ===================================================================
# Geo & Period Configuration
# ===================================================================


class TestGeoPeriodConfig:
    """Configurable geo and period for Google Trends API calls."""

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_uses_configured_geo(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """TrendReq is called with the configured geo value."""
        import pandas as pd
        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = pd.DataFrame({0: ["test"]})

        await selector._fetch_trends()

        # Verify geo was passed to TrendReq constructor
        _, kwargs = mock_trend_req.call_args
        assert kwargs.get("geo") == "US"

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_uses_configured_period(
        self, mock_trend_req: MagicMock, selector: TrendSelector, db_pool: AsyncMock
    ):
        """build_payload is called with the configured timeframe."""
        import pandas as pd
        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = pd.DataFrame({0: ["test"]})

        await selector._fetch_trends()

        # Verify build_payload was called with timeframe
        instance.build_payload.assert_called_once_with(
            kw_list=[], timeframe="now 1-d"
        )

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

    @patch("modules.trend_selector.HAS_PYTRENDS", True)
    @patch("modules.trend_selector.TrendReq")
    async def test_empty_geo_passed_through(
        self, mock_trend_req: MagicMock, db_pool: AsyncMock
    ):
        """Empty string geo is passed through (worldwide)."""
        import pandas as pd
        sel = TrendSelector(db_pool, {
            "backup_trends": [],
            "trend_history_days": 30,
            "geo": "",
            "period": "now 1-d",
        })
        instance = mock_trend_req.return_value
        instance.trending_searches.return_value = pd.DataFrame({0: ["test"]})

        await sel._fetch_trends()

        _, kwargs = mock_trend_req.call_args
        assert kwargs.get("geo") == ""
