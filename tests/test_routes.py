"""Tests for app/routes.py — FastAPI endpoints.

Covers:
- Dashboard (GET /)
- Option detail (GET /options/{id})
- Approve option (POST /options/{id}/approve)
- Cancel option (POST /options/{id}/cancel)
- Mark as Posted (POST /options/{id}/mark-posted)
- Regenerate text (POST /options/{id}/regenerate-text)
- Regenerate image (POST /options/{id}/regenerate-image)
- Preview (GET /preview/{id})
- Platform preview (GET /preview/{id}/{platform})
- History (GET /history)
- Health check (GET /health)
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
    """Test client with mocked DB dependencies and no lifespan.

    We create a fresh FastAPI app, attach the router directly,
    and mock all ``app.routes`` DB helpers so no real database is needed.
    The lifespan is intentionally omitted to avoid real DB connections.
    """
    with patch("app.routes.fetch", new_callable=AsyncMock) as mock_fetch, \
         patch("app.routes.fetch_one", new_callable=AsyncMock) as mock_fetch_one, \
         patch("app.routes.execute", new_callable=AsyncMock) as mock_execute, \
         patch("app.routes.transaction") as mock_transaction:

        # Build a minimal app with only the router (no lifespan)
        from app.routes import router

        test_app = FastAPI()
        test_app.include_router(router)

        # Set up the transaction mock to return a mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 42})
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        # transaction() returns an async context manager
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_transaction.return_value = mock_cm

        with TestClient(test_app) as test_client:
            test_client.mock_fetch = mock_fetch
            test_client.mock_fetch_one = mock_fetch_one
            test_client.mock_execute = mock_execute
            test_client.mock_transaction = mock_transaction
            test_client.mock_conn = mock_conn
            yield test_client


def _make_row(**overrides) -> dict:
    """Create a mock database row dict."""
    row = {
        "id": 1,
        "batch_id": "batch_test",
        "platform": "pinterest",
        "theme": "Crispy Cooking",
        "fact": "Air fryers use rapid air technology to create crispy food.",
        "hashtags": ["#AirFryer", "#Healthy"],
        "image_prompt": "A warm shot of food.",
        "image_path": "test.png",
        "status": "pending",
        "created_at": None,
        "updated_at": None,
    }
    row.update(overrides)
    return row


# ===================================================================
# Dashboard
# ===================================================================


class TestDashboard:
    """Dashboard endpoint tests."""

    def test_dashboard_returns_html(self, client: TestClient):
        client.mock_fetch.return_value = []
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_with_platform_filter(self, client: TestClient):
        client.mock_fetch.return_value = []
        response = client.get("/?platform=pinterest")
        assert response.status_code == 200

    def test_dashboard_shows_options(self, client: TestClient):
        client.mock_fetch.return_value = [_make_row()]
        response = client.get("/")
        assert response.status_code == 200
        assert "Crispy Cooking" in response.text


# ===================================================================
# Option Detail
# ===================================================================


class TestOptionDetail:
    """Option detail endpoint tests."""

    def test_detail_found(self, client: TestClient):
        client.mock_fetch_one.return_value = _make_row()
        response = client.get("/options/1")
        assert response.status_code == 200
        assert "Crispy Cooking" in response.text

    def test_detail_not_found(self, client: TestClient):
        client.mock_fetch_one.return_value = None
        response = client.get("/options/999")
        assert response.status_code == 404


# ===================================================================
# Approve
# ===================================================================


class TestApprove:
    """Approve endpoint tests."""

    def test_approve_success(self, client: TestClient):
        client.mock_execute.return_value = "UPDATE 1"
        response = client.post("/options/1/approve", follow_redirects=False)
        assert response.status_code == 302  # Redirect

    def test_approve_not_found(self, client: TestClient):
        client.mock_execute.return_value = "UPDATE 0"
        response = client.post("/options/999/approve")
        assert response.status_code == 409


# ===================================================================
# Cancel
# ===================================================================


class TestCancel:
    """Cancel endpoint tests."""

    def test_cancel_success(self, client: TestClient):
        client.mock_execute.return_value = "UPDATE 1"
        response = client.post("/options/1/cancel", follow_redirects=False)
        assert response.status_code == 302

    def test_cancel_not_found(self, client: TestClient):
        client.mock_execute.return_value = "UPDATE 0"
        response = client.post("/options/999/cancel")
        assert response.status_code == 409


# ===================================================================
# Mark as Posted
# ===================================================================


class TestMarkPosted:
    """Mark as Posted endpoint tests."""

    def test_mark_posted_success(self, client: TestClient):
        """Valid approved option → returns 200, creates post record, updates status.

        Two fetch_one calls are made: first checks existence, second checks approved status.
        """
        # First call (existence check) returns a row; second call (approved status) returns full data
        client.mock_fetch_one.side_effect = [
            {"id": 1},  # exists
            {            # approved + data
                "id": 1,
                "platform": "pinterest",
                "image_path": "test.png",
            },
        ]
        response = client.post("/options/1/mark-posted")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Post marked as posted"
        assert data["post_id"] == 42

        # Verify transaction was used with correct SQL
        client.mock_conn.fetchrow.assert_called_once()
        call_args = client.mock_conn.fetchrow.call_args
        assert "INSERT INTO posts" in call_args[0][0]
        assert call_args[0][1] == 1  # content_option_id
        assert call_args[0][2] == "pinterest"  # platform
        assert call_args[0][3] == "test.png"  # image_path

        client.mock_conn.execute.assert_called_once()
        call_args = client.mock_conn.execute.call_args
        assert "UPDATE content_options" in call_args[0][0]
        assert "posted" in call_args[0][0]
        assert call_args[0][1] == 1

    def test_mark_posted_not_found(self, client: TestClient):
        """Non-existent id → first fetch_one returns None → returns 404."""
        client.mock_fetch_one.return_value = None
        response = client.post("/options/999/mark-posted")
        assert response.status_code == 404
        assert response.json()["detail"] == "Content option not found"

    def test_mark_posted_not_approved(self, client: TestClient):
        """Option in 'pending' status → exists but not approved → returns 409."""
        client.mock_fetch_one.side_effect = [
            {"id": 1},  # exists
            None,        # not approved
        ]
        response = client.post("/options/1/mark-posted")
        assert response.status_code == 409
        assert response.json()["detail"] == "Option not found or not in approved status"

    def test_mark_posted_already_posted(self, client: TestClient):
        """Option already 'posted' → exists but not approved → returns 409."""
        client.mock_fetch_one.side_effect = [
            {"id": 1},  # exists
            None,        # not approved
        ]
        response = client.post("/options/1/mark-posted")
        assert response.status_code == 409
        assert response.json()["detail"] == "Option not found or not in approved status"

    def test_mark_posted_cancelled(self, client: TestClient):
        """Cancelled option → exists but not approved → returns 409."""
        client.mock_fetch_one.side_effect = [
            {"id": 1},  # exists
            None,        # not approved
        ]
        response = client.post("/options/1/mark-posted")
        assert response.status_code == 409
        assert response.json()["detail"] == "Option not found or not in approved status"

    def test_mark_posted_transaction_failure(self, client: TestClient):
        """DB transaction fails → both fetch_ones succeed → returns 500."""
        client.mock_fetch_one.side_effect = [
            {"id": 1},  # exists
            {            # approved + data
                "id": 1,
                "platform": "pinterest",
                "image_path": "test.png",
            },
        ]
        client.mock_conn.fetchrow.side_effect = Exception("DB connection lost")
        response = client.post("/options/1/mark-posted")
        assert response.status_code == 500
        assert "Failed to mark post as posted" in response.json()["detail"]


# ===================================================================
# Preview — Button Visibility
# ===================================================================


class TestPreviewButtons:
    """Preview page button visibility tests."""

    def test_preview_shows_buttons_for_approved(self, client: TestClient):
        """Approved pinterest option → buttons present in HTML."""
        client.mock_fetch_one.return_value = _make_row(status="approved")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "Post to Pinterest" in response.text
        assert "Mark as Posted" in response.text

    def test_preview_hides_buttons_for_pending(self, client: TestClient):
        """Pending option → buttons absent."""
        client.mock_fetch_one.return_value = _make_row(status="pending")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "Post to Pinterest" not in response.text
        assert "Mark as Posted" not in response.text

    def test_preview_hides_buttons_for_posted(self, client: TestClient):
        """Posted option → buttons absent."""
        client.mock_fetch_one.return_value = _make_row(status="posted")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "Post to Pinterest" not in response.text
        assert "Mark as Posted" not in response.text

    def test_preview_hides_buttons_for_instagram(self, client: TestClient):
        """Instagram approved option → buttons absent (pinterest only)."""
        client.mock_fetch_one.return_value = _make_row(status="approved", platform="instagram")
        response = client.get("/preview/1/instagram")
        assert response.status_code == 200
        assert "Post to Pinterest" not in response.text
        assert "Mark as Posted" not in response.text


# ===================================================================
# Regenerate Text
# ===================================================================


class TestRegenerateText:
    """Regenerate text endpoint tests."""

    def test_regenerate_text_not_found(self, client: TestClient):
        client.mock_fetch_one.return_value = None
        response = client.post("/options/999/regenerate-text")
        assert response.status_code == 404


# ===================================================================
# Regenerate Image
# ===================================================================


class TestRegenerateImage:
    """Regenerate image endpoint tests."""

    def test_regenerate_image_not_found(self, client: TestClient):
        client.mock_fetch_one.return_value = None
        response = client.post("/options/999/regenerate-image")
        assert response.status_code == 404

    def test_regenerate_image_no_prompt(self, client: TestClient):
        client.mock_fetch_one.return_value = _make_row(image_prompt=None)
        response = client.post("/options/1/regenerate-image")
        assert response.status_code == 400


# ===================================================================
# Preview
# ===================================================================


class TestPreview:
    """Preview endpoint tests."""

    def test_preview_found(self, client: TestClient):
        client.mock_fetch_one.return_value = _make_row()
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_preview_not_found(self, client: TestClient):
        client.mock_fetch_one.return_value = None
        response = client.get("/preview/999")
        assert response.status_code == 404

    def test_platform_preview_found(self, client: TestClient):
        client.mock_fetch_one.return_value = _make_row()
        response = client.get("/preview/1/pinterest")
        assert response.status_code == 200

    def test_platform_preview_not_found(self, client: TestClient):
        client.mock_fetch_one.return_value = None
        response = client.get("/preview/999/instagram")
        assert response.status_code == 404


# ===================================================================
# History
# ===================================================================


class TestHistory:
    """History endpoint tests."""

    def test_history_returns_html(self, client: TestClient):
        client.mock_fetch.return_value = []
        response = client.get("/history")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_history_with_platform_filter(self, client: TestClient):
        client.mock_fetch.return_value = []
        response = client.get("/history?platform=pinterest")
        assert response.status_code == 200


# ===================================================================
# Health
# ===================================================================


class TestHealth:
    """Health check endpoint tests."""

    def test_health_returns_json(self, client: TestClient):
        client.mock_fetch.return_value = [{"1": 1}]
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] is True
        assert "timestamp" in data

    def test_health_degraded(self, client: TestClient):
        client.mock_fetch.side_effect = Exception("DB error")
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] is False
