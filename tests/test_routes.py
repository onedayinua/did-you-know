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
# Posted Page
# ===================================================================


class TestPostedPage:
    """Posted page endpoint tests."""

    def test_posted_returns_html(self, client: TestClient):
        """Verify /posted returns 200 OK with HTML content type."""
        client.mock_fetch.return_value = []
        response = client.get("/posted")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_posted_shows_only_posted_options(self, client: TestClient):
        """Verify only posted options are returned by checking the query uses status='posted'."""
        client.mock_fetch.return_value = []
        response = client.get("/posted")
        assert response.status_code == 200
        # Confirm the fetch was called with a query containing status = 'posted'
        call_args = client.mock_fetch.call_args
        assert call_args is not None
        query = call_args[0][0]
        assert "status = 'posted'" in query or "status=$1" in query

    def test_posted_displays_posted_options(self, client: TestClient):
        """Verify posted options appear in the rendered HTML."""
        client.mock_fetch.return_value = [
            _make_row(status="posted", theme="Posted Fact #1"),
            _make_row(status="posted", theme="Posted Fact #2", platform="instagram"),
        ]
        response = client.get("/posted")
        assert response.status_code == 200
        assert "Posted Fact #1" in response.text
        assert "Posted Fact #2" in response.text

    def test_posted_with_platform_filter(self, client: TestClient):
        """Verify platform filter is passed through for posted page."""
        client.mock_fetch.return_value = []
        response = client.get("/posted?platform=pinterest")
        assert response.status_code == 200
        call_args = client.mock_fetch.call_args
        assert call_args is not None
        assert call_args[0][1] == "pinterest"  # second arg is the platform value

    def test_posted_empty_state(self, client: TestClient):
        """Verify empty state message when no posted options exist."""
        client.mock_fetch.return_value = []
        response = client.get("/posted")
        assert response.status_code == 200
        assert "No posted posts yet" in response.text

    def test_posted_contains_preview_links(self, client: TestClient):
        """Verify each posted option has a preview button linking to /preview/{id}."""
        client.mock_fetch.return_value = [
            _make_row(id=1, status="posted"),
            _make_row(id=2, status="posted", platform="instagram"),
        ]
        response = client.get("/posted")
        assert response.status_code == 200
        assert '/preview/1' in response.text
        assert '/preview/2' in response.text

    def test_posted_contains_posted_badge(self, client: TestClient):
        """Verify posted options display the 'posted' status badge."""
        client.mock_fetch.return_value = [
            _make_row(status="posted"),
        ]
        response = client.get("/posted")
        assert response.status_code == 200
        assert 'status-badge posted' in response.text

    def test_posted_menu_link_present(self, client: TestClient):
        """Verify the 'Posted' menu link exists in the navigation."""
        client.mock_fetch.return_value = []
        response = client.get("/posted")
        assert response.status_code == 200
        assert '<a href="/posted">Posted</a>' in response.text
        assert '<a href="/approved">Approved</a>' in response.text
        assert '<a href="/history">History</a>' in response.text

    def test_posted_shows_heading(self, client: TestClient):
        """Verify the page heading says 'Posted Content'."""
        client.mock_fetch.return_value = []
        response = client.get("/posted")
        assert response.status_code == 200
        assert "Posted Content" in response.text


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
# Preview — UI Layout & Approve/Cancel Buttons (TKT-031)
# ===================================================================


class TestPreviewUI:
    """Preview page UI layout and approve/cancel button visibility tests."""

    def test_preview_layout_has_two_columns(self, client: TestClient):
        """Pending option → HTML contains two-column layout classes."""
        client.mock_fetch_one.return_value = _make_row(status="pending")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert 'class="preview-layout"' in response.text
        assert 'class="preview-body-wrapper"' in response.text
        assert 'class="preview-image-wrapper"' in response.text

    def test_preview_shows_approve_for_pending(self, client: TestClient):
        """Pending option → Approve button (<button id="approve-btn">) present."""
        client.mock_fetch_one.return_value = _make_row(status="pending")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert 'id="approve-btn"' in response.text

    def test_preview_shows_cancel_for_pending(self, client: TestClient):
        """Pending option → Cancel button (<button id="cancel-btn">) present."""
        client.mock_fetch_one.return_value = _make_row(status="pending")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert 'id="cancel-btn"' in response.text

    def test_preview_shows_cancel_for_approved(self, client: TestClient):
        """Approved option → Cancel button present, Approve button absent."""
        client.mock_fetch_one.return_value = _make_row(status="approved")
        response = client.get("/preview/1")
        assert response.status_code == 200
        # Cancel button should be rendered as an HTML element
        assert 'id="cancel-btn"' in response.text
        # Approve button should NOT be rendered as an HTML element
        # (JS code may reference 'approve-btn' but the HTML <button> must not exist)
        html_lower = response.text.lower()
        assert '<button id="approve-btn"' not in html_lower

    def test_preview_hides_approve_cancel_for_posted(self, client: TestClient):
        """Posted option → neither Approve nor Cancel buttons rendered."""
        client.mock_fetch_one.return_value = _make_row(status="posted")
        response = client.get("/preview/1")
        assert response.status_code == 200
        # JS code may reference 'approve-btn' / 'cancel-btn' but HTML buttons must not exist
        html_lower = response.text.lower()
        assert '<button id="approve-btn"' not in html_lower
        assert '<button id="cancel-btn"' not in html_lower

    def test_preview_hides_approve_cancel_for_cancelled(self, client: TestClient):
        """Cancelled option → neither Approve nor Cancel buttons rendered."""
        client.mock_fetch_one.return_value = _make_row(status="cancelled")
        response = client.get("/preview/1")
        assert response.status_code == 200
        html_lower = response.text.lower()
        assert '<button id="approve-btn"' not in html_lower
        assert '<button id="cancel-btn"' not in html_lower

    def test_preview_image_on_right_side(self, client: TestClient):
        """Verify HTML order: preview-body-wrapper before preview-image-wrapper."""
        client.mock_fetch_one.return_value = _make_row(status="pending")
        response = client.get("/preview/1")
        assert response.status_code == 200
        html = response.text
        body_idx = html.index('class="preview-body-wrapper"')
        image_idx = html.index('class="preview-image-wrapper"')
        assert body_idx < image_idx, (
            "preview-body-wrapper should appear before preview-image-wrapper in the DOM"
        )

    def test_preview_approve_json_accept_header(self, client: TestClient):
        """Approve with Accept: application/json → returns JSON, not redirect."""
        client.mock_execute.return_value = "UPDATE 1"
        response = client.post(
            "/options/1/approve",
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Content option approved"

    def test_preview_cancel_json_accept_header(self, client: TestClient):
        """Cancel with Accept: application/json → returns JSON, not redirect."""
        client.mock_execute.return_value = "UPDATE 1"
        response = client.post(
            "/options/1/cancel",
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Content option cancelled"

    def test_preview_approve_redirect_without_json(self, client: TestClient):
        """Approve without Accept: application/json → still returns redirect."""
        client.mock_execute.return_value = "UPDATE 1"
        response = client.post("/options/1/approve", follow_redirects=False)
        assert response.status_code == 302

    def test_preview_cancel_redirect_without_json(self, client: TestClient):
        """Cancel without Accept: application/json → still returns redirect."""
        client.mock_execute.return_value = "UPDATE 1"
        response = client.post("/options/1/cancel", follow_redirects=False)
        assert response.status_code == 302


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


# ===================================================================
# Validate Text
# ===================================================================


class TestValidateText:
    """Validate text endpoint tests."""

    def test_validate_text_success(self, client: TestClient):
        client.mock_fetch_one.return_value = {
            "id": 1,
            "fact": "Air fryers use rapid air technology.",
            "hashtags": ["#AirFryer", "#Healthy"],
            "img_title": "Crispy Air Fryer Tips",
        }

        with patch("shared.db.get_pool") as mock_get_pool, \
             patch("shared.openrouter_client.OpenRouterClient") as mock_client_cls, \
             patch("shared.config_loader.get_content_template") as mock_get_config, \
             patch("modules.text_validator.TextValidator") as mock_validator_cls:

            mock_pool = AsyncMock()
            mock_get_pool.return_value = mock_pool

            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            mock_get_config.return_value = {"validation": {"enabled": True}}

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = {
                "toxicity_score": 0.95,
                "politeness_score": 0.90,
                "grammar_score": 0.85,
                "sentiment_score": 0.80,
                "readability_score": 0.88,
                "img_title_score": 0.92,
            }
            mock_validator_cls.return_value = mock_validator

            response = client.post("/options/1/validate-text")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["scores"]["toxicity_score"] == 0.95
            assert data["scores"]["politeness_score"] == 0.90
            assert data["scores"]["grammar_score"] == 0.85
            assert data["scores"]["sentiment_score"] == 0.80
            assert data["scores"]["readability_score"] == 0.88
            assert data["scores"]["img_title_score"] == 0.92

    def test_validate_text_not_found(self, client: TestClient):
        client.mock_fetch_one.return_value = None
        response = client.post("/options/999/validate-text")
        assert response.status_code == 404

    def test_validate_text_handles_empty_hashtags(self, client: TestClient):
        client.mock_fetch_one.return_value = {
            "id": 1,
            "fact": "Air fryers use rapid air technology.",
            "hashtags": [],
            "img_title": "Crispy Air Fryer Tips",
        }

        with patch("shared.db.get_pool") as mock_get_pool, \
             patch("shared.openrouter_client.OpenRouterClient") as mock_client_cls, \
             patch("shared.config_loader.get_content_template") as mock_get_config, \
             patch("modules.text_validator.TextValidator") as mock_validator_cls:

            mock_get_pool.return_value = AsyncMock()
            mock_client_cls.return_value = AsyncMock()
            mock_get_config.return_value = {"validation": {"enabled": True}}

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = {
                "toxicity_score": 0.95,
                "politeness_score": 0.90,
                "grammar_score": 0.85,
                "sentiment_score": 0.80,
                "readability_score": 0.88,
                "img_title_score": 0.92,
            }
            mock_validator_cls.return_value = mock_validator

            response = client.post("/options/1/validate-text")
            assert response.status_code == 200

    def test_validate_text_handles_string_hashtags(self, client: TestClient):
        client.mock_fetch_one.return_value = {
            "id": 1,
            "fact": "Air fryers use rapid air technology.",
            "hashtags": '["#AirFryer", "#Healthy"]',
            "img_title": "Crispy Air Fryer Tips",
        }

        with patch("shared.db.get_pool") as mock_get_pool, \
             patch("shared.openrouter_client.OpenRouterClient") as mock_client_cls, \
             patch("shared.config_loader.get_content_template") as mock_get_config, \
             patch("modules.text_validator.TextValidator") as mock_validator_cls:

            mock_get_pool.return_value = AsyncMock()
            mock_client_cls.return_value = AsyncMock()
            mock_get_config.return_value = {"validation": {"enabled": True}}

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = {
                "toxicity_score": 0.95,
                "politeness_score": 0.90,
                "grammar_score": 0.85,
                "sentiment_score": 0.80,
                "readability_score": 0.88,
                "img_title_score": 0.92,
            }
            mock_validator_cls.return_value = mock_validator

            response = client.post("/options/1/validate-text")
            assert response.status_code == 200


# ===================================================================
# Regenerate Text Preview
# ===================================================================


class TestRegenerateTextPreview:
    """Regenerate text preview endpoint tests.

    Tests:
    - Success: valid pending option -> 200, updates fact/hashtags/img_title
    - Not found: non-existent id -> 404
    - Not pending: approved/posted option -> 409
    """

    def test_regenerate_text_preview_success(self, client: TestClient):
        """Valid pending option -> returns 200 with task_id."""
        client.mock_fetch_one.side_effect = [
            {"id": 1, "theme": "Crispy Cooking", "platform": "pinterest"},
            {"id": 1, "status": "pending"},
        ]

        with patch("shared.db.get_pool") as mock_get_pool, \
             patch("shared.openrouter_client.OpenRouterClient") as mock_client_cls, \
             patch("shared.config_loader.get_content_template") as mock_get_config, \
             patch("modules.content_generator.ContentGenerator") as mock_generator_cls, \
             patch("modules.text_validator.TextValidator") as mock_validator_cls:

            mock_pool = AsyncMock()
            mock_get_pool.return_value = mock_pool

            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            mock_get_config.return_value = {
                "platforms": {"pinterest": {"character_limit": 500, "hashtag_count": "5-10"}},
                "validation": {"enabled": True},
            }

            mock_generator = AsyncMock()
            mock_generator._generate_text_variations.return_value = [
                {
                    "fact": "Air fryers use rapid air technology to create crispy food.",
                    "hashtags": ["#AirFryer", "#Healthy"],
                    "img_title": "Crispy Air Fryer Tips",
                }
            ]
            mock_generator_cls.return_value = mock_generator

            mock_validator = AsyncMock()
            mock_validator.validate.return_value = {
                "toxicity_score": 0.95,
                "politeness_score": 0.90,
                "grammar_score": 0.85,
                "sentiment_score": 0.80,
                "readability_score": 0.88,
                "img_title_score": 0.92,
            }
            mock_validator_cls.return_value = mock_validator

            response = client.post("/options/1/regenerate-text-preview")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["message"] == "Text regeneration started"
            assert "task_id" in data
            assert len(data["task_id"]) > 0

    def test_regenerate_text_preview_not_found(self, client: TestClient):
        """Non-existent id -> first fetch_one returns None -> 404."""
        client.mock_fetch_one.return_value = None
        response = client.post("/options/999/regenerate-text-preview")
        assert response.status_code == 404
        assert response.json()["detail"] == "Content option not found"

    def test_regenerate_text_preview_not_pending(self, client: TestClient):
        """Approved/posted option -> 409."""
        client.mock_fetch_one.side_effect = [
            {"id": 1, "theme": "Test", "platform": "pinterest"},
            {"id": 1, "status": "approved"},
        ]
        response = client.post("/options/1/regenerate-text-preview")
        assert response.status_code == 409
        assert "pending" in response.json()["detail"]


# ===================================================================
# Regenerate Image Preview
# ===================================================================


class TestRegenerateImagePreview:
    """Regenerate image preview endpoint tests.

    Tests:
    - Success: valid pending option with image_prompt -> 200
    - Not found: non-existent id -> 404
    - Not pending: approved/posted option -> 409
    - No prompt: option without image_prompt -> 400
    """

    def test_regenerate_image_preview_success(self, client: TestClient):
        """Valid pending option with image_prompt -> 200 with image_path."""
        client.mock_fetch_one.side_effect = [
            {
                "id": 1,
                "batch_id": "batch_test",
                "platform": "pinterest",
                "image_prompt": "A warm shot of food.",
                "img_title": "Crispy Air Fryer Tips",
            },
            {"id": 1, "status": "pending"},
        ]

        with patch("shared.db.get_pool") as mock_get_pool, \
             patch("shared.openrouter_client.OpenRouterClient") as mock_client_cls, \
             patch("shared.config_loader.get_platforms_config") as mock_get_config, \
             patch("modules.visual_generator.VisualGenerator") as mock_generator_cls:

            mock_pool = AsyncMock()
            mock_get_pool.return_value = mock_pool

            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            mock_get_config.return_value = {
                "visual": {"dimensions": {"pinterest": {"width": 1000, "height": 1500}}},
            }

            mock_generator = AsyncMock()
            mock_generator._generate_and_save.return_value = "data/images/batch_test_1.png"
            mock_generator._update_image_path = AsyncMock()
            mock_generator._get_dimensions.return_value = {"width": 1000, "height": 1500}
            mock_generator_cls.return_value = mock_generator

            response = client.post("/options/1/regenerate-image-preview")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["message"] == "Image regeneration started"
            assert "image_path" in data
            assert len(data["image_path"]) > 0

    def test_regenerate_image_preview_not_found(self, client: TestClient):
        """Non-existent id -> first fetch_one returns None -> 404."""
        client.mock_fetch_one.return_value = None
        response = client.post("/options/999/regenerate-image-preview")
        assert response.status_code == 404
        assert response.json()["detail"] == "Content option not found"

    def test_regenerate_image_preview_not_pending(self, client: TestClient):
        """Approved/posted option -> 409."""
        client.mock_fetch_one.side_effect = [
            {
                "id": 1,
                "batch_id": "batch_test",
                "platform": "pinterest",
                "image_prompt": "A warm shot of food.",
                "img_title": "Test",
            },
            {"id": 1, "status": "approved"},
        ]
        response = client.post("/options/1/regenerate-image-preview")
        assert response.status_code == 409
        assert "pending" in response.json()["detail"]

    def test_regenerate_image_preview_no_prompt(self, client: TestClient):
        """Option without image_prompt -> 400."""
        client.mock_fetch_one.side_effect = [
            {
                "id": 1,
                "batch_id": "batch_test",
                "platform": "pinterest",
                "image_prompt": None,
                "img_title": "Test",
            },
            {"id": 1, "status": "pending"},
        ]
        response = client.post("/options/1/regenerate-image-preview")
        assert response.status_code == 400
        assert "image prompt" in response.json()["detail"].lower()


# ===================================================================
# Preview - Regenerate Button Visibility
# ===================================================================


class TestPreviewRegenerateButtons:
    """Preview page regenerate button visibility tests."""

    def test_preview_shows_buttons_for_pending(self, client: TestClient):
        """Pending option -> regenerate buttons present in HTML."""
        client.mock_fetch_one.return_value = _make_row(status="pending")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "Regenerate Text" in response.text
        assert "Regenerate Image" in response.text

    def test_preview_hides_buttons_for_approved(self, client: TestClient):
        """Approved option -> regenerate buttons absent."""
        client.mock_fetch_one.return_value = _make_row(status="approved")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "Regenerate Text" not in response.text
        assert "Regenerate Image" not in response.text

    def test_preview_shows_img_title(self, client: TestClient):
        """Option with img_title set -> img_title displayed."""
        client.mock_fetch_one.return_value = _make_row(img_title="Test Title")
        response = client.get("/preview/1")
        assert response.status_code == 200
        assert "Image Title:" in response.text
        assert "Test Title" in response.text

    def test_preview_hides_img_title_when_empty(self, client: TestClient):
        """Option without img_title -> img_title not displayed."""
        client.mock_fetch_one.return_value = _make_row(img_title=None, status="approved")
        response = client.get("/preview/1")
        assert response.status_code == 200
        # The img_title display div should not be rendered
        assert '<strong>Image Title:</strong> {{ option.img_title }}' not in response.text
        # But "Image Title:" might appear in JS for pending status - use approved status
        # to ensure no img_title block is rendered
        assert '<strong>Image Title:</strong>' not in response.text
