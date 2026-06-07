"""Tests for app/routes.py — FastAPI endpoints.

Covers:
- Dashboard (GET /)
- Option detail (GET /options/{id})
- Approve option (POST /options/{id}/approve)
- Cancel option (POST /options/{id}/cancel)
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
         patch("app.routes.execute", new_callable=AsyncMock) as mock_execute:

        # Build a minimal app with only the router (no lifespan)
        from app.routes import router

        test_app = FastAPI()
        test_app.include_router(router)

        with TestClient(test_app) as test_client:
            test_client.mock_fetch = mock_fetch
            test_client.mock_fetch_one = mock_fetch_one
            test_client.mock_execute = mock_execute
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
