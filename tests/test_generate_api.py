"""Tests for app/routes.py — content generation endpoints.

Covers:
- POST /generate — trigger content generation
- GET /generate/status — poll generation status
- WebSocket /generate/ws — real-time status updates
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def client():
    """Test client with mocked DB and scheduler dependencies.

    The generate endpoints use lazy imports inside the handler, so we
    patch at the source modules (shared.db, shared.openrouter_client,
    shared.config_loader, app.scheduler) instead of app.routes.

    We import app submodules up front so that unittest.mock.patch can
    resolve dotted paths like ``app.routes.fetch``.
    """
    import app.routes  # noqa: F811 — register on app module for mock
    import app.scheduler  # noqa: F811 — register on app module for mock

    with (
        patch("app.routes.fetch", new_callable=AsyncMock) as mock_fetch,
        patch("app.routes.fetch_one", new_callable=AsyncMock) as mock_fetch_one,
        patch("app.routes.execute", new_callable=AsyncMock) as mock_execute,
        patch("app.routes.transaction") as mock_transaction,
    ):
        from app.routes import router

        test_app = FastAPI()
        test_app.include_router(router)

        # Mock transaction
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 42})
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_transaction.return_value = mock_cm

        with TestClient(test_app) as test_client:
            test_client.mock_fetch = mock_fetch
            test_client.mock_fetch_one = mock_fetch_one
            test_client.mock_execute = mock_execute
            yield test_client


def _make_pool_mock():
    """Create a mock pool that supports async context manager acquire()."""
    pool = AsyncMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    # Make pool.acquire() return the context manager (not an async callable)
    type(pool).acquire = MagicMock(return_value=cm)
    return pool, conn


# ===================================================================
# POST /generate
# ===================================================================


class TestTriggerGeneration:
    """POST /generate endpoint tests."""

    def test_generate_starts_when_idle(self, client: TestClient):
        """Returns 202 when generation is triggered from idle state."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("shared.openrouter_client.OpenRouterClient") as mock_openrouter_cls,
            patch("shared.config_loader.load_config") as mock_load_config,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
            patch("app.scheduler.update_generation_state", new_callable=AsyncMock) as mock_update_state,
            patch("app.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run_pipeline,
        ):
            mock_get_state.return_value = {
                "status": "idle", "progress_message": "", "error_message": "", "updated_at": "",
            }
            mock_load_config.side_effect = lambda name: {
                "content_template": {"text_prompt": "test"},
                "platforms": {"platforms": {"pinterest": {"enabled": True}}},
                "backup_trends": {"backup_trends": [{"keyword": "test", "score": 85}]},
            }.get(name, {})
            client_instance = AsyncMock()
            client_instance.close = AsyncMock()
            mock_openrouter_cls.return_value = client_instance

            response = client.post("/generate")
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "started"
            mock_update_state.assert_called_once()

    def test_generate_returns_409_when_running(self, client: TestClient):
        """Returns 409 when generation is already running."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool),
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "running", "progress_message": "Selecting trend...",
                "error_message": "", "updated_at": "2024-01-01T00:00:00",
            }
            response = client.post("/generate")
            assert response.status_code == 409
            data = response.json()
            assert "already in progress" in data["detail"].lower()

    def test_generate_allows_completed_to_restart(self, client: TestClient):
        """Completed status allows a new generation to start."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("shared.openrouter_client.OpenRouterClient") as mock_openrouter_cls,
            patch("shared.config_loader.load_config") as mock_load_config,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
            patch("app.scheduler.update_generation_state", new_callable=AsyncMock) as mock_update_state,
            patch("app.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run_pipeline,
        ):
            mock_get_state.return_value = {
                "status": "completed", "progress_message": "Done!",
                "error_message": "", "updated_at": "",
            }
            mock_load_config.side_effect = lambda name: {
                "content_template": {"text_prompt": "test"},
                "platforms": {"platforms": {"pinterest": {"enabled": True}}},
                "backup_trends": {"backup_trends": [{"keyword": "test", "score": 85}]},
            }.get(name, {})
            client_instance = AsyncMock()
            client_instance.close = AsyncMock()
            mock_openrouter_cls.return_value = client_instance

            response = client.post("/generate")
            assert response.status_code == 202

    def test_generate_allows_failed_to_restart(self, client: TestClient):
        """Failed status allows a new generation to start."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("shared.openrouter_client.OpenRouterClient") as mock_openrouter_cls,
            patch("shared.config_loader.load_config") as mock_load_config,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
            patch("app.scheduler.update_generation_state", new_callable=AsyncMock) as mock_update_state,
            patch("app.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run_pipeline,
        ):
            mock_get_state.return_value = {
                "status": "failed", "progress_message": "Error",
                "error_message": "Error", "updated_at": "",
            }
            mock_load_config.side_effect = lambda name: {
                "content_template": {"text_prompt": "test"},
                "platforms": {"platforms": {"pinterest": {"enabled": True}}},
                "backup_trends": {"backup_trends": [{"keyword": "test", "score": 85}]},
            }.get(name, {})
            client_instance = AsyncMock()
            client_instance.close = AsyncMock()
            mock_openrouter_cls.return_value = client_instance

            response = client.post("/generate")
            assert response.status_code == 202

    def test_generate_sets_running_state(self, client: TestClient):
        """Verifies update_generation_state is called with 'running'."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("shared.openrouter_client.OpenRouterClient") as mock_openrouter_cls,
            patch("shared.config_loader.load_config") as mock_load_config,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
            patch("app.scheduler.update_generation_state", new_callable=AsyncMock) as mock_update_state,
            patch("app.scheduler.run_pipeline", new_callable=AsyncMock) as mock_run_pipeline,
        ):
            mock_get_state.return_value = {
                "status": "idle", "progress_message": "", "error_message": "", "updated_at": "",
            }
            mock_load_config.side_effect = lambda name: {
                "content_template": {"text_prompt": "test"},
                "platforms": {"platforms": {"pinterest": {"enabled": True}}},
                "backup_trends": {"backup_trends": [{"keyword": "test", "score": 85}]},
            }.get(name, {})
            client_instance = AsyncMock()
            client_instance.close = AsyncMock()
            mock_openrouter_cls.return_value = client_instance

            client.post("/generate")
            call_args = mock_update_state.call_args
            assert call_args is not None
            # Second positional arg should be "running"
            assert call_args[0][1] == "running"


# ===================================================================
# GET /generate/status
# ===================================================================


class TestGenerationStatus:
    """GET /generate/status endpoint tests."""

    def test_status_idle(self, client: TestClient):
        """Returns idle status when no generation is running."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "idle", "progress_message": "", "error_message": "", "updated_at": "",
            }
            response = client.get("/generate/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "idle"

    def test_status_running(self, client: TestClient):
        """Returns running status with progress message."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "running", "progress_message": "Selecting trend...",
                "error_message": "", "updated_at": "2024-01-01T00:00:00",
            }
            response = client.get("/generate/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["message"] == "Selecting trend..."

    def test_status_completed(self, client: TestClient):
        """Returns completed status."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "completed", "progress_message": "Pipeline complete! 3 options generated for 1 platforms",
                "error_message": "", "updated_at": "2024-01-01T00:00:00",
            }
            response = client.get("/generate/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert "Pipeline complete" in data["message"]

    def test_status_failed(self, client: TestClient):
        """Returns failed status with error message."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "failed", "progress_message": "Failed: No trend found",
                "error_message": "No trend found", "updated_at": "2024-01-01T00:00:00",
            }
            response = client.get("/generate/status")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["error_message"] == "No trend found"

    def test_status_includes_updated_at(self, client: TestClient):
        """Response includes updated_at timestamp."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "idle", "progress_message": "", "error_message": "",
                "updated_at": "2024-06-20T12:00:00+00:00",
            }
            response = client.get("/generate/status")
            data = response.json()
            assert "updated_at" in data
            assert data["updated_at"] == "2024-06-20T12:00:00+00:00"


# ===================================================================
# POST /generate/reset
# ===================================================================


class TestResetGeneration:
    """POST /generate/reset endpoint tests."""

    def test_reset_clears_running_state(self, client: TestClient):
        """POST /generate/reset clears a running state."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.reset_generation_state", new_callable=AsyncMock) as mock_reset,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            # First set up the mock to say it was running
            mock_get_state.return_value = {
                "status": "idle", "progress_message": "", "updated_at": "2024-06-20T12:00:00+00:00",
            }

            # Reset
            response = client.post("/generate/reset")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "idle"

            # Verify reset_generation_state was called
            mock_reset.assert_called_once()

    def test_reset_returns_idle_when_already_idle(self, client: TestClient):
        """POST /generate/reset works even when already idle."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.reset_generation_state", new_callable=AsyncMock) as mock_reset,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.return_value = {
                "status": "idle", "progress_message": "", "updated_at": "2024-06-20T12:00:00+00:00",
            }

            response = client.post("/generate/reset")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "idle"
            mock_reset.assert_called_once()


# ===================================================================
# WebSocket /generate/ws
# ===================================================================


class TestGenerationWebSocket:
    """WebSocket /generate/ws endpoint tests."""

    def test_websocket_sends_status_updates(self, client: TestClient):
        """WebSocket sends status updates while generation is running."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            # First call returns running, second returns completed
            mock_get_state.side_effect = [
                {
                    "status": "running",
                    "progress_message": "Selecting trend...",
                    "error_message": "",
                    "updated_at": "2024-01-01T00:00:00",
                },
                {
                    "status": "completed",
                    "progress_message": "Pipeline complete!",
                    "error_message": "",
                    "updated_at": "2024-01-01T00:01:00",
                },
            ]

            with client.websocket_connect("/generate/ws") as ws:
                # First message — running
                data = ws.receive_json()
                assert data["status"] == "running"
                assert "message" in data
                assert "updated_at" in data

                # Second message — completed (causes WS to close)
                data = ws.receive_json()
                assert data["status"] == "completed"
                assert "message" in data

    def test_websocket_closes_on_failed(self, client: TestClient):
        """WebSocket closes when status transitions to failed."""
        pool, conn = _make_pool_mock()

        with (
            patch("shared.db.get_pool", new_callable=AsyncMock, return_value=pool) as mock_get_pool,
            patch("app.scheduler.get_generation_state", new_callable=AsyncMock) as mock_get_state,
        ):
            mock_get_state.side_effect = [
                {
                    "status": "running",
                    "progress_message": "Selecting trend...",
                    "error_message": "",
                    "updated_at": "2024-01-01T00:00:00",
                },
                {
                    "status": "failed",
                    "progress_message": "Failed: No trend found",
                    "error_message": "No trend found",
                    "updated_at": "2024-01-01T00:01:00",
                },
            ]

            with client.websocket_connect("/generate/ws") as ws:
                data = ws.receive_json()
                assert data["status"] == "running"

                data = ws.receive_json()
                assert data["status"] == "failed"
                assert "error_message" in data