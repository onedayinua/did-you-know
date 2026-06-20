"""Tests for app/scheduler.py — pipeline orchestration.

Covers:
- ``run_pipeline()`` — full pipeline orchestration (mocked)
- ``setup_scheduler()`` — scheduler configuration
- ``update_generation_state()`` — state persistence
- ``get_generation_state()`` — state retrieval
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scheduler import run_pipeline, setup_scheduler, update_generation_state, get_generation_state
from shared.models import Trend, Theme


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def db_pool() -> AsyncMock:
    """Mock asyncpg connection pool."""
    pool = AsyncMock()
    pool.fetch = AsyncMock()
    pool.fetch_one = AsyncMock()
    pool.fetchval = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.fixture
def openrouter_client() -> AsyncMock:
    """Mock OpenRouterClient."""
    client = AsyncMock()
    client.generate_text = AsyncMock()
    client.generate_image = AsyncMock()
    return client


@pytest.fixture
def sample_config() -> dict:
    """Full config dict for pipeline."""
    return {
        "content_template": {
            "text_prompt": "Theme is '{theme}'",
            "image_prompt": "Image for '{fact}'",
            "platforms": {
                "pinterest": {"character_limit": 500, "hashtag_count": "5-10"},
            },
            "variations": 1,
            "queue": {"max_pending": 10, "expire_days": 7, "cleanup_on_generate": True},
        },
        "platforms": {
            "platforms": {
                "pinterest": {"enabled": True, "api_base": "https://api.pinterest.com/v5"},
                "instagram": {"enabled": False, "api_base": "https://graph.instagram.com"},
            },
            "visual": {
                "model": "openai/dall-e-3",
                "dimensions": {
                    "pinterest": {"width": 1000, "height": 1500},
                },
            },
        },
        "backup_trends": {
            "backup_trends": [{"keyword": "easy dinner recipes", "score": 85.0}],
            "trend_history_days": 30,
            "queue": {"max_pending": 10, "expire_days": 7, "cleanup_on_generate": True},
        },
    }


# ===================================================================
# Generation State Helpers
# ===================================================================


class TestGenerationState:
    """Generation state persistence tests."""

    def _make_conn(self, fetchrow_return=None, execute_return="UPDATE 1"):
        """Create a mock connection with context manager support."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=fetchrow_return)
        conn.execute = AsyncMock(return_value=execute_return)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return conn, cm

    async def test_update_generation_state_inserts_when_no_row(
        self, db_pool: AsyncMock
    ):
        """First call inserts a new row."""
        # Simulate no existing row
        conn, cm = self._make_conn(fetchrow_return=None, execute_return="INSERT 0 1")
        # Make pool.acquire() return the context manager (not async)
        type(db_pool).acquire = MagicMock(return_value=cm)

        await update_generation_state(db_pool, "running", "Testing...")

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "INSERT INTO generation_state" in call_args[0][0]
        assert call_args[0][1] == "running"
        assert call_args[0][2] == "Testing..."

    async def test_update_generation_state_updates_existing_row(
        self, db_pool: AsyncMock
    ):
        """Subsequent calls update the existing row."""
        conn, cm = self._make_conn(fetchrow_return={"id": 1})
        type(db_pool).acquire = MagicMock(return_value=cm)

        await update_generation_state(db_pool, "completed", "Done!")

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert "UPDATE generation_state" in call_args[0][0]
        assert call_args[0][1] == "completed"
        assert call_args[0][2] == "Done!"

    async def test_get_generation_state_returns_default_when_no_table(
        self, db_pool: AsyncMock
    ):
        """When the table doesn't exist, returns idle default."""
        type(db_pool).acquire = MagicMock(side_effect=Exception("relation does not exist"))

        state = await get_generation_state(db_pool)

        assert state["status"] == "idle"
        assert state["progress_message"] == ""

    async def test_get_generation_state_returns_row(self, db_pool: AsyncMock):
        """Returns the current state row."""
        conn, cm = self._make_conn(
            fetchrow_return={
                "status": "running",
                "progress_message": "Selecting trend...",
                "error_message": "",
                "updated_at": None,
            }
        )
        type(db_pool).acquire = MagicMock(return_value=cm)

        state = await get_generation_state(db_pool)

        assert state["status"] == "running"
        assert state["progress_message"] == "Selecting trend..."

    async def test_update_with_error_message(self, db_pool: AsyncMock):
        """Error message is stored when status is failed."""
        conn, cm = self._make_conn(fetchrow_return={"id": 1})
        type(db_pool).acquire = MagicMock(return_value=cm)

        await update_generation_state(
            db_pool, "failed", "Something broke", error_message="Something broke"
        )

        call_args = conn.execute.call_args
        assert call_args[0][1] == "failed"
        assert call_args[0][3] == "Something broke"


# ===================================================================
# run_pipeline
# ===================================================================


class TestRunPipeline:
    """Full pipeline orchestration (mocked)."""

    @patch("modules.trend_selector.TrendSelector")
    @patch("modules.theme_associator.ThemeAssociator")
    @patch("modules.content_generator.ContentGenerator")
    @patch("modules.visual_generator.VisualGenerator")
    async def test_full_successful_flow(
        self,
        mock_vg: MagicMock,
        mock_cg: MagicMock,
        mock_ta: MagicMock,
        mock_ts: MagicMock,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_config: dict,
    ):
        """All steps complete successfully."""
        # Mock TrendSelector
        ts_instance = mock_ts.return_value
        ts_instance.run = AsyncMock(return_value=Trend(id=1, keyword="air fryer recipes", score=90.0, source="google_trends"))

        # Mock ThemeAssociator
        ta_instance = mock_ta.return_value
        ta_instance.run = AsyncMock(return_value=Theme(id=1, name="Crispy Cooking", trend_id=1))

        # Mock ContentGenerator
        cg_instance = mock_cg.return_value
        cg_instance.run = AsyncMock(return_value=[
            MagicMock(id=1, spec=["id"]),
            MagicMock(id=2, spec=["id"]),
        ])

        # Mock VisualGenerator
        vg_instance = mock_vg.return_value
        vg_instance.run = AsyncMock(return_value=[])

        result = await run_pipeline(db_pool, openrouter_client, sample_config)

        assert result["status"] == "completed"
        assert result["trend"] == "air fryer recipes"
        assert result["theme"] == "Crispy Cooking"
        assert result["platforms"] == ["pinterest"]
        assert result["options_generated"] == 2

        # Verify all modules were called
        ts_instance.run.assert_called_once()
        ta_instance.run.assert_called_once()
        cg_instance.run.assert_called_once()
        vg_instance.run.assert_called_once()

    @patch("modules.trend_selector.TrendSelector")
    async def test_skips_when_no_trend(
        self,
        mock_ts: MagicMock,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_config: dict,
    ):
        """Pipeline skips when no trend is found."""
        ts_instance = mock_ts.return_value
        ts_instance.run = AsyncMock(return_value=None)

        result = await run_pipeline(db_pool, openrouter_client, sample_config)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_trend_found"

    @patch("modules.trend_selector.TrendSelector")
    @patch("modules.theme_associator.ThemeAssociator")
    async def test_skips_when_no_platforms_enabled(
        self,
        mock_ta: MagicMock,
        mock_ts: MagicMock,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_config: dict,
    ):
        """Pipeline skips when no platforms are enabled."""
        ts_instance = mock_ts.return_value
        ts_instance.run = AsyncMock(return_value=Trend(id=1, keyword="test", score=50.0, source="test"))

        ta_instance = mock_ta.return_value
        ta_instance.run = AsyncMock(return_value=Theme(id=1, name="Test", trend_id=1))

        # Disable all platforms
        config = dict(sample_config)
        config["platforms"] = {
            "platforms": {
                "pinterest": {"enabled": False},
                "instagram": {"enabled": False},
            },
        }

        result = await run_pipeline(db_pool, openrouter_client, config)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_platforms_enabled"

    @patch("modules.trend_selector.TrendSelector")
    @patch("modules.theme_associator.ThemeAssociator")
    @patch("modules.content_generator.ContentGenerator")
    async def test_skips_when_queue_full(
        self,
        mock_cg: MagicMock,
        mock_ta: MagicMock,
        mock_ts: MagicMock,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        sample_config: dict,
    ):
        """Pipeline skips when content generator returns empty (queue full)."""
        ts_instance = mock_ts.return_value
        ts_instance.run = AsyncMock(return_value=Trend(id=1, keyword="test", score=50.0, source="test"))

        ta_instance = mock_ta.return_value
        ta_instance.run = AsyncMock(return_value=Theme(id=1, name="Test", trend_id=1))

        cg_instance = mock_cg.return_value
        cg_instance.run = AsyncMock(return_value=[])

        result = await run_pipeline(db_pool, openrouter_client, sample_config)

        assert result["status"] == "skipped"
        assert result["reason"] == "queue_full"


# ===================================================================
# setup_scheduler
# ===================================================================


class TestSetupScheduler:
    """Scheduler configuration tests."""

    def test_adds_job(self, db_pool: AsyncMock, openrouter_client: AsyncMock, sample_config: dict):
        """setup_scheduler adds a job to the scheduler."""
        from app.scheduler import scheduler

        # Clear any existing jobs
        scheduler.remove_all_jobs()

        setup_scheduler(db_pool, openrouter_client, sample_config)

        jobs = scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert "content_pipeline" in job_ids

        # Clean up
        scheduler.remove_all_jobs()
