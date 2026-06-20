"""Tests for modules/visual_generator.py — VisualGenerator class.

Covers:
- ``_get_pending_options()`` — query for options needing images
- ``_get_dimensions()`` — platform-specific dimension lookup
- ``_get_dalle_size()`` — DALL-E size string mapping
- ``_generate_and_save()`` — image generation + file write (mocked)
- ``_update_image_path()`` — database update
- ``run()`` — full pipeline (mocked)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.visual_generator import VisualGenerator, ASPECT_RATIO_MAP
from shared.models import ContentOption, ContentStatus


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def sample_config() -> dict:
    """Full config dict as loaded from platforms.yaml."""
    return {
        "visual": {
            "model": "openai/dall-e-3",
            "image_size": "0.5K",
            "dimensions": {
                "pinterest": {
                    "width": 500,
                    "height": 1000,
                    "aspect_ratio": "2:3",
                    "output_megapixels": 1.0,
                },
                "instagram": {"width": 1080, "height": 1080},
            },
        },
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
def openrouter_client() -> AsyncMock:
    """Mock OpenRouterClient with generate_image."""
    client = AsyncMock()
    client.generate_image = AsyncMock()
    return client


@pytest.fixture
def generator(
    db_pool: AsyncMock,
    openrouter_client: AsyncMock,
    sample_config: dict,
) -> VisualGenerator:
    """VisualGenerator instance with mocked dependencies."""
    return VisualGenerator(db_pool, openrouter_client, sample_config)


@pytest.fixture
def sample_option() -> ContentOption:
    """Sample ContentOption model for testing."""
    return ContentOption(
        id=1,
        batch_id="batch_20240101_000000_abc123",
        platform="pinterest",
        theme="Crispy Cooking",
        fact="Air fryers use rapid air technology.",
        hashtags=["#AirFryer"],
        image_prompt="A warm overhead shot of crispy chicken wings.",
        image_path=None,
        status=ContentStatus.PENDING,
    )


# ===================================================================
# _get_pending_options
# ===================================================================


class TestGetPendingOptions:
    """Query for options needing images."""

    async def test_returns_all_pending_when_no_ids(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Returns all pending options when no specific IDs are given."""
        db_pool.fetch.return_value = [
            {
                "id": 1,
                "batch_id": "b1",
                "platform": "pinterest",
                "theme": "Test",
                "fact": "Fact",
                "hashtags": ["#t"],
                "image_prompt": "prompt",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        result = await generator._get_pending_options(None)
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].platform.value == "pinterest"

    async def test_returns_specific_ids(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Returns only the options matching the given IDs."""
        db_pool.fetch.return_value = [
            {
                "id": 2,
                "batch_id": "b2",
                "platform": "instagram",
                "theme": "Test",
                "fact": "Fact",
                "hashtags": [],
                "image_prompt": "prompt",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        result = await generator._get_pending_options([2])
        assert len(result) == 1
        assert result[0].id == 2

    async def test_returns_empty_when_none_pending(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Returns empty list when no rows match."""
        db_pool.fetch.return_value = []
        result = await generator._get_pending_options(None)
        assert result == []

    async def test_filters_status_and_image_path(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Only pending options without image_path are returned."""
        db_pool.fetch.return_value = [
            {
                "id": 10,
                "batch_id": "b10",
                "platform": "pinterest",
                "theme": "Filtered",
                "fact": "Fact",
                "hashtags": [],
                "image_prompt": "prompt",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        result = await generator._get_pending_options(None)
        assert len(result) == 1
        assert result[0].id == 10
        assert result[0].status == ContentStatus.PENDING
        assert result[0].image_path is None


# ===================================================================
# _get_dimensions
# ===================================================================


class TestGetDimensions:
    """Platform-specific dimension lookup."""

    def test_returns_pinterest_dimensions(self, generator: VisualGenerator):
        """Pinterest returns 500x1000."""
        dims = generator._get_dimensions("pinterest")
        assert dims["width"] == 500
        assert dims["height"] == 1000

    def test_returns_instagram_dimensions(self, generator: VisualGenerator):
        """Instagram returns 1080x1080."""
        dims = generator._get_dimensions("instagram")
        assert dims["width"] == 1080
        assert dims["height"] == 1080

    def test_returns_default_for_unknown_platform(self, generator: VisualGenerator):
        """Unknown platform defaults to 1024x1024."""
        dims = generator._get_dimensions("unknown")
        assert dims["width"] == 1024
        assert dims["height"] == 1024

    def test_uses_config_defaults_when_partial(self, generator: VisualGenerator):
        """Partial platform config uses 1024 defaults for missing keys."""
        gen = VisualGenerator(
            generator._db,
            generator._client,
            {
                "visual": {
                    "dimensions": {
                        "custom": {"width": 800},
                    },
                },
            },
        )
        dims = gen._get_dimensions("custom")
        assert dims["width"] == 800
        assert dims["height"] == 1024

    def test_aspect_ratio_derived_from_pinterest(self, generator: VisualGenerator):
        """Aspect ratio derived from Pinterest config explicit aspect_ratio (2:3)."""
        ratio = generator._get_aspect_ratio("pinterest")
        assert ratio == "2:3"

    def test_aspect_ratio_derived_from_instagram(self, generator: VisualGenerator):
        """Aspect ratio derived from Instagram dimensions (1080x1080 = 1:1)."""
        ratio = generator._get_aspect_ratio("instagram")
        assert ratio == "1:1"

    def test_aspect_ratio_fallback_to_map(self, generator: VisualGenerator):
        """Unknown platform falls back to ASPECT_RATIO_MAP then 1:1."""
        ratio = generator._get_aspect_ratio("unknown")
        assert ratio == "1:1"


# ===================================================================
# _get_aspect_ratio
# ===================================================================


class TestGetAspectRatio:
    """Aspect ratio string mapping."""

    def test_returns_pinterest_ratio(self, generator: VisualGenerator):
        """Pinterest maps to 2:3."""
        assert generator._get_aspect_ratio("pinterest") == "2:3"

    def test_returns_instagram_ratio(self, generator: VisualGenerator):
        """Instagram maps to 1:1."""
        assert generator._get_aspect_ratio("instagram") == "1:1"

    def test_returns_default_for_unknown(self, generator: VisualGenerator):
        """Unknown platform defaults to 1:1."""
        assert generator._get_aspect_ratio("unknown") == "1:1"


# ===================================================================
# _get_output_megapixels
# ===================================================================


class TestOutputMegapixels:
    """Output megapixels lookup."""

    def test_returns_pinterest_megapixels(self, generator: VisualGenerator):
        mp = generator._get_output_megapixels("pinterest")
        assert mp == 1.0

    def test_returns_none_when_not_configured(self, generator: VisualGenerator):
        mp = generator._get_output_megapixels("unknown")
        assert mp is None

    def test_returns_none_when_zero(self, generator, db_pool, openrouter_client):
        gen = VisualGenerator(db_pool, openrouter_client, {
            "visual": {
                "dimensions": {
                    "custom": {"output_megapixels": 0},
                },
            },
        })
        mp = gen._get_output_megapixels("custom")
        assert mp is None


# ===================================================================
# _generate_and_save
# ===================================================================


class TestGenerateAndSave:
    """Image generation + file write (mocked)."""

    async def test_generates_and_saves(
        self,
        generator: VisualGenerator,
        openrouter_client: AsyncMock,
        sample_option: ContentOption,
        tmp_path: Path,
    ):
        """Image is generated and written to disk at the expected path."""
        generator._images_dir = str(tmp_path)
        openrouter_client.generate_image.return_value = b"fake_image_bytes"

        result = await generator._generate_and_save(
            sample_option, {"width": 500, "height": 1000}
        )

        assert "batch_20240101_000000_abc123_1.png" in result
        # Verify file was written at the expected location
        filepath = Path(generator._images_dir) / result
        assert filepath.exists()
        assert filepath.read_bytes() == b"fake_image_bytes"

    async def test_raises_on_generation_failure(
        self,
        generator: VisualGenerator,
        openrouter_client: AsyncMock,
        sample_option: ContentOption,
    ):
        """Raises when the image generation API call fails."""
        openrouter_client.generate_image.side_effect = Exception("API error")
        with pytest.raises(Exception, match="API error"):
            await generator._generate_and_save(
                sample_option, {"width": 500, "height": 1000}
            )

    async def test_raises_on_write_failure(
        self,
        generator: VisualGenerator,
        openrouter_client: AsyncMock,
        sample_option: ContentOption,
    ):
        """Raises RuntimeError when the image file cannot be written."""
        generator._images_dir = "/nonexistent/directory"
        openrouter_client.generate_image.return_value = b"bytes"
        with pytest.raises(RuntimeError, match="Failed to write image file"):
            await generator._generate_and_save(
                sample_option, {"width": 500, "height": 1000}
            )

    async def test_passes_correct_parameters(
        self,
        generator: VisualGenerator,
        openrouter_client: AsyncMock,
        sample_option: ContentOption,
        tmp_path: Path,
    ):
        """generate_image is called with the right prompt, model, aspect_ratio, and output_megapixels."""
        generator._images_dir = str(tmp_path)
        openrouter_client.generate_image.return_value = b"bytes"

        await generator._generate_and_save(
            sample_option, {"width": 500, "height": 1000}
        )

        openrouter_client.generate_image.assert_called_once_with(
            prompt=sample_option.image_prompt,
            model="openai/dall-e-3",
            aspect_ratio="2:3",
            size="0.5K",
            output_megapixels=1.0,
        )


# ===================================================================
# _update_image_path
# ===================================================================


class TestUpdateImagePath:
    """Database update operations."""

    async def test_updates_image_path(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Executes UPDATE query with image_path and option_id."""
        db_pool.execute.return_value = "UPDATE 1"
        await generator._update_image_path(1, "data/images/test.png")
        db_pool.execute.assert_called_once()
        query = db_pool.execute.call_args[0][0]
        assert "UPDATE" in query
        assert "image_path" in query

    async def test_logs_warning_when_no_row_updated(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Logs a warning when no row is updated (non-existent ID)."""
        db_pool.execute.return_value = "UPDATE 0"
        # Should not raise, just log warning
        await generator._update_image_path(999, "data/images/test.png")

    async def test_passes_correct_parameters(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Verifies the SQL query and parameters passed to the DB."""
        db_pool.execute.return_value = "UPDATE 1"
        await generator._update_image_path(42, "data/images/my_image.png")

        db_pool.execute.assert_called_once()
        args = db_pool.execute.call_args[0]
        assert "UPDATE content_options" in args[0]
        assert "data/images/my_image.png" in args
        assert 42 in args


# ===================================================================
# run() — full pipeline
# ===================================================================


class TestRun:
    """Full pipeline integration tests (mocked)."""

    async def test_full_successful_flow(
        self,
        generator: VisualGenerator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        tmp_path: Path,
    ):
        """Full flow: fetch pending -> generate -> save -> update DB -> return updated options."""
        generator._images_dir = str(tmp_path)
        db_pool.fetch.return_value = [
            {
                "id": 1,
                "batch_id": "batch_test",
                "platform": "pinterest",
                "theme": "Test",
                "fact": "Fact",
                "hashtags": ["#t"],
                "image_prompt": "A test prompt",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        openrouter_client.generate_image.return_value = b"image_bytes"
        db_pool.execute.return_value = "UPDATE 1"

        result = await generator.run()

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].image_path is not None
        assert "batch_test_1.png" in result[0].image_path

    async def test_returns_empty_when_no_pending(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Returns empty list when no pending options need images."""
        db_pool.fetch.return_value = []
        result = await generator.run()
        assert result == []

    async def test_handles_specific_ids(
        self,
        generator: VisualGenerator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        tmp_path: Path,
    ):
        """Processes only the content option IDs passed to run()."""
        generator._images_dir = str(tmp_path)
        db_pool.fetch.return_value = [
            {
                "id": 5,
                "batch_id": "batch_5",
                "platform": "instagram",
                "theme": "Test",
                "fact": "Fact",
                "hashtags": [],
                "image_prompt": "prompt",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        openrouter_client.generate_image.return_value = b"img"
        db_pool.execute.return_value = "UPDATE 1"

        result = await generator.run([5])
        assert len(result) == 1
        assert result[0].id == 5

    async def test_continues_on_partial_failure(
        self,
        generator: VisualGenerator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        tmp_path: Path,
    ):
        """Continues processing remaining options when one fails."""
        generator._images_dir = str(tmp_path)
        db_pool.fetch.return_value = [
            {
                "id": 1,
                "batch_id": "b1",
                "platform": "pinterest",
                "theme": "T1",
                "fact": "F1",
                "hashtags": [],
                "image_prompt": "p1",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
            {
                "id": 2,
                "batch_id": "b2",
                "platform": "instagram",
                "theme": "T2",
                "fact": "F2",
                "hashtags": [],
                "image_prompt": "p2",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        # First succeeds, second fails
        openrouter_client.generate_image.side_effect = [
            b"image_bytes",
            Exception("API error"),
        ]
        db_pool.execute.return_value = "UPDATE 1"

        result = await generator.run()
        # Should have 1 successful result (the second one failed)
        assert len(result) == 1
        assert result[0].id == 1

    async def test_uses_platform_dimensions(
        self,
        generator: VisualGenerator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        tmp_path: Path,
    ):
        """Uses platform-specific dimensions from config."""
        generator._images_dir = str(tmp_path)
        db_pool.fetch.return_value = [
            {
                "id": 3,
                "batch_id": "b3",
                "platform": "instagram",
                "theme": "T3",
                "fact": "F3",
                "hashtags": [],
                "image_prompt": "p3",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        openrouter_client.generate_image.return_value = b"img"
        db_pool.execute.return_value = "UPDATE 1"

        result = await generator.run()
        assert len(result) == 1
        # Instagram aspect ratio should be 1:1
        openrouter_client.generate_image.assert_called_once_with(
            prompt="p3",
            model="openai/dall-e-3",
            aspect_ratio="1:1",
            size="0.5K",
            output_megapixels=None,
        )


# ===================================================================
# Edge cases
# ===================================================================


class TestEdgeCases:
    """Additional edge-case coverage."""

    def test_aspect_ratio_map_has_all_platforms(self):
        """ASPECT_RATIO_MAP covers all supported platforms."""
        assert "pinterest" in ASPECT_RATIO_MAP
        assert "instagram" in ASPECT_RATIO_MAP

    def test_generator_with_empty_config(
        self, db_pool: AsyncMock, openrouter_client: AsyncMock
    ):
        """Generator works with an empty config using defaults."""
        gen = VisualGenerator(db_pool, openrouter_client, {})
        assert gen._model == "openai/dall-e-3"
        dims = gen._get_dimensions("pinterest")
        assert dims["width"] == 1024

    async def test_run_with_no_image_prompt(
        self, generator: VisualGenerator, db_pool: AsyncMock
    ):
        """Returns empty list when no options have image_prompt."""
        db_pool.fetch.return_value = []
        result = await generator.run()
        assert result == []

    async def test_run_creates_images_dir(
        self,
        generator: VisualGenerator,
        db_pool: AsyncMock,
        openrouter_client: AsyncMock,
        tmp_path: Path,
    ):
        """Creates the images directory if it does not exist."""
        images_dir = tmp_path / "new_images"
        generator._images_dir = str(images_dir)
        assert not images_dir.exists()

        db_pool.fetch.return_value = [
            {
                "id": 7,
                "batch_id": "b7",
                "platform": "pinterest",
                "theme": "T7",
                "fact": "F7",
                "hashtags": [],
                "image_prompt": "p7",
                "image_path": None,
                "status": "pending",
                "created_at": None,
                "updated_at": None,
            },
        ]
        openrouter_client.generate_image.return_value = b"bytes"
        db_pool.execute.return_value = "UPDATE 1"

        await generator.run()
        assert images_dir.exists()
