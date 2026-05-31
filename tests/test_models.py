"""Tests for shared/models.py — Pydantic v2 data models."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.models import (
    ApproveRequest,
    CancelRequest,
    ContentOption,
    ContentOptionResponse,
    ContentStatus,
    HealthResponse,
    Platform,
    Post,
    PostResponse,
    PostStatus,
    RegenerateImageRequest,
    RegenerateTextRequest,
    Theme,
    Trend,
    content_option_from_record,
    post_from_record,
    theme_from_record,
    trend_from_record,
)


# ===================================================================
# Enum Tests
# ===================================================================


class TestContentStatus:
    """Verify ContentStatus enum values."""

    def test_values(self):
        assert ContentStatus.PENDING.value == "pending"
        assert ContentStatus.APPROVED.value == "approved"
        assert ContentStatus.POSTED.value == "posted"
        assert ContentStatus.EXPIRED.value == "expired"
        assert ContentStatus.CANCELLED.value == "cancelled"

    def test_members(self):
        assert len(ContentStatus) == 5


class TestPostStatus:
    """Verify PostStatus enum values."""

    def test_values(self):
        assert PostStatus.PENDING.value == "pending"
        assert PostStatus.SUCCESS.value == "success"
        assert PostStatus.FAILED.value == "failed"

    def test_members(self):
        assert len(PostStatus) == 3


class TestPlatform:
    """Verify Platform enum values."""

    def test_values(self):
        assert Platform.PINTEREST.value == "pinterest"
        assert Platform.INSTAGRAM.value == "instagram"

    def test_members(self):
        assert len(Platform) == 2


# ===================================================================
# Trend Model Tests
# ===================================================================


class TestTrend:
    """Test Trend model creation and validation."""

    def test_valid_creation(self):
        """Valid Trend with all required fields."""
        trend = Trend(keyword="AI art", score=85.5)
        assert trend.keyword == "AI art"
        assert trend.score == 85.5
        assert trend.source == "google_trends"  # default
        assert trend.id is None
        assert trend.created_at is None

    def test_valid_with_all_fields(self):
        """Valid Trend with optional fields populated."""
        dt = datetime.now(timezone.utc)
        trend = Trend(
            id=1,
            keyword="machine learning",
            score=92.0,
            source="custom",
            created_at=dt,
        )
        assert trend.id == 1
        assert trend.keyword == "machine learning"
        assert trend.score == 92.0
        assert trend.source == "custom"
        assert trend.created_at == dt

    def test_invalid_score_below_zero(self):
        """Score < 0 should raise ValidationError."""
        with pytest.raises(ValidationError):
            Trend(keyword="test", score=-1.0)

    def test_invalid_score_above_100(self):
        """Score > 100 should raise ValidationError."""
        with pytest.raises(ValidationError):
            Trend(keyword="test", score=100.1)

    def test_score_boundary_values(self):
        """Boundary values for score (0.0 and 100.0)."""
        t1 = Trend(keyword="test", score=0.0)
        assert t1.score == 0.0
        t2 = Trend(keyword="test", score=100.0)
        assert t2.score == 100.0

    def test_missing_required_keyword(self):
        """Missing keyword should raise ValidationError."""
        with pytest.raises(ValidationError):
            Trend(score=50.0)  # type: ignore[call-arg]

    def test_empty_keyword(self):
        """Empty keyword (min_length=1) should raise ValidationError."""
        with pytest.raises(ValidationError):
            Trend(keyword="", score=50.0)

    def test_keyword_too_long(self):
        """Keyword exceeding max_length should raise ValidationError."""
        with pytest.raises(ValidationError):
            Trend(keyword="x" * 256, score=50.0)

    def test_source_too_long(self):
        """Source exceeding max_length should raise ValidationError."""
        with pytest.raises(ValidationError):
            Trend(keyword="test", score=50.0, source="x" * 51)

    def test_from_attributes_enabled(self):
        """Config.from_attributes should be True for ORM compatibility."""
        assert Trend.model_config.get("from_attributes") is True


# ===================================================================
# Theme Model Tests
# ===================================================================


class TestTheme:
    """Test Theme model creation and validation."""

    def test_valid_creation(self):
        """Valid Theme with all required fields."""
        theme = Theme(name="AI Art Trends", trend_id=1)
        assert theme.name == "AI Art Trends"
        assert theme.trend_id == 1
        assert theme.id is None
        assert theme.created_at is None

    def test_valid_with_all_fields(self):
        """Valid Theme with optional fields populated."""
        dt = datetime.now(timezone.utc)
        theme = Theme(id=5, name="Tech News", trend_id=3, created_at=dt)
        assert theme.id == 5
        assert theme.name == "Tech News"
        assert theme.trend_id == 3
        assert theme.created_at == dt

    def test_empty_name(self):
        """Empty name (min_length=1) should raise ValidationError."""
        with pytest.raises(ValidationError):
            Theme(name="", trend_id=1)

    def test_name_too_long(self):
        """Name exceeding max_length should raise ValidationError."""
        with pytest.raises(ValidationError):
            Theme(name="x" * 101, trend_id=1)

    def test_missing_trend_id(self):
        """Missing trend_id should raise ValidationError."""
        with pytest.raises(ValidationError):
            Theme(name="test")  # type: ignore[call-arg]

    def test_from_attributes_enabled(self):
        """Config.from_attributes should be True."""
        assert Theme.model_config.get("from_attributes") is True


# ===================================================================
# ContentOption Model Tests
# ===================================================================


class TestContentOption:
    """Test ContentOption model creation and validation."""

    def test_valid_creation(self):
        """Valid ContentOption with all required fields."""
        option = ContentOption(
            batch_id="batch-001",
            platform=Platform.PINTEREST,
            theme="AI Art",
            fact="AI-generated art is transforming creative industries.",
        )
        assert option.batch_id == "batch-001"
        assert option.platform == Platform.PINTEREST
        assert option.theme == "AI Art"
        assert option.fact == "AI-generated art is transforming creative industries."
        assert option.hashtags == []  # default
        assert option.status == ContentStatus.PENDING  # default
        assert option.id is None
        assert option.image_prompt is None
        assert option.image_path is None
        assert option.created_at is None
        assert option.updated_at is None

    def test_valid_with_all_fields(self):
        """Valid ContentOption with all optional fields populated."""
        dt = datetime.now(timezone.utc)
        option = ContentOption(
            id=10,
            batch_id="batch-002",
            platform=Platform.INSTAGRAM,
            theme="Cooking Tips",
            fact="Did you know that...",
            hashtags=["#cooking", "#tips"],
            image_prompt="A chef cooking",
            image_path="/images/chef.png",
            status=ContentStatus.APPROVED,
            created_at=dt,
            updated_at=dt,
        )
        assert option.id == 10
        assert option.platform == Platform.INSTAGRAM
        assert option.hashtags == ["#cooking", "#tips"]
        assert option.status == ContentStatus.APPROVED

    def test_platform_as_string_enum_value(self):
        """Platform can be created from string enum value."""
        option = ContentOption(
            batch_id="b1",
            platform="pinterest",
            theme="Test",
            fact="A fact.",
        )
        assert option.platform == Platform.PINTEREST

    def test_platform_as_invalid_string(self):
        """Invalid platform string should raise ValidationError."""
        with pytest.raises(ValidationError):
            ContentOption(
                batch_id="b1",
                platform="twitter",  # not in Platform enum
                theme="Test",
                fact="A fact.",
            )

    def test_empty_fact(self):
        """Empty fact (min_length=1) should raise ValidationError."""
        with pytest.raises(ValidationError):
            ContentOption(
                batch_id="b1",
                platform=Platform.PINTEREST,
                theme="Test",
                fact="",
            )

    def test_empty_theme(self):
        """Empty theme (min_length=1) should raise ValidationError."""
        with pytest.raises(ValidationError):
            ContentOption(
                batch_id="b1",
                platform=Platform.PINTEREST,
                theme="",
                fact="A fact.",
            )

    def test_batch_id_too_long(self):
        """Batch_id exceeding max_length should raise ValidationError."""
        with pytest.raises(ValidationError):
            ContentOption(
                batch_id="x" * 51,
                platform=Platform.PINTEREST,
                theme="Test",
                fact="A fact.",
            )

    def test_default_hashtags_is_empty_list(self):
        """Default hashtags should be an empty list, not None."""
        option = ContentOption(
            batch_id="b1",
            platform=Platform.PINTEREST,
            theme="Test",
            fact="A fact.",
        )
        assert option.hashtags == []
        assert isinstance(option.hashtags, list)

    def test_default_status_is_pending(self):
        """Default status should be ContentStatus.PENDING."""
        option = ContentOption(
            batch_id="b1",
            platform=Platform.PINTEREST,
            theme="Test",
            fact="A fact.",
        )
        assert option.status == ContentStatus.PENDING

    def test_from_attributes_enabled(self):
        """Config.from_attributes should be True."""
        assert ContentOption.model_config.get("from_attributes") is True


# ===================================================================
# Post Model Tests
# ===================================================================


class TestPost:
    """Test Post model creation and validation."""

    def test_valid_creation(self):
        """Valid Post with all required fields."""
        post = Post(content_option_id=1, platform="pinterest")
        assert post.content_option_id == 1
        assert post.platform == "pinterest"
        assert post.status == PostStatus.PENDING  # default
        assert post.id is None
        assert post.image_path is None
        assert post.post_url is None
        assert post.error is None
        assert post.created_at is None
        assert post.updated_at is None

    def test_valid_with_all_fields(self):
        """Valid Post with all optional fields populated."""
        dt = datetime.now(timezone.utc)
        post = Post(
            id=42,
            content_option_id=10,
            platform="instagram",
            image_path="/images/post.png",
            status=PostStatus.SUCCESS,
            post_url="https://instagram.com/p/abc123",
            error=None,
            created_at=dt,
            updated_at=dt,
        )
        assert post.id == 42
        assert post.platform == "instagram"
        assert post.status == PostStatus.SUCCESS
        assert post.post_url == "https://instagram.com/p/abc123"

    def test_failed_post_with_error(self):
        """Post with FAILED status and error message."""
        post = Post(
            content_option_id=5,
            platform="pinterest",
            status=PostStatus.FAILED,
            error="API rate limit exceeded",
        )
        assert post.status == PostStatus.FAILED
        assert post.error == "API rate limit exceeded"

    def test_missing_content_option_id(self):
        """Missing content_option_id should raise ValidationError."""
        with pytest.raises(ValidationError):
            Post(platform="pinterest")  # type: ignore[call-arg]

    def test_missing_platform(self):
        """Missing platform should raise ValidationError."""
        with pytest.raises(ValidationError):
            Post(content_option_id=1)  # type: ignore[call-arg]

    def test_platform_too_long(self):
        """Platform exceeding max_length should raise ValidationError."""
        with pytest.raises(ValidationError):
            Post(content_option_id=1, platform="x" * 51)

    def test_default_status(self):
        """Default status should be PostStatus.PENDING."""
        post = Post(content_option_id=1, platform="pinterest")
        assert post.status == PostStatus.PENDING

    def test_from_attributes_enabled(self):
        """Config.from_attributes should be True."""
        assert Post.model_config.get("from_attributes") is True


# ===================================================================
# API Model Tests
# ===================================================================


class TestContentOptionResponse:
    """Test ContentOptionResponse API model."""

    def test_valid_creation(self):
        """Valid ContentOptionResponse with all fields."""
        dt = datetime.now(timezone.utc)
        resp = ContentOptionResponse(
            id=1,
            batch_id="batch-001",
            platform="pinterest",
            theme="AI Art",
            fact="AI art is transforming industries.",
            hashtags=["#AI", "#art"],
            image_prompt="An AI creating art",
            image_url="http://example.com/img.png",
            status=ContentStatus.APPROVED,
            created_at=dt,
            updated_at=dt,
        )
        assert resp.id == 1
        assert resp.platform == "pinterest"
        assert resp.image_url == "http://example.com/img.png"
        assert resp.status == ContentStatus.APPROVED

    def test_image_url_default_none(self):
        """image_url should default to None."""
        dt = datetime.now(timezone.utc)
        resp = ContentOptionResponse(
            id=1,
            batch_id="b1",
            platform="pinterest",
            theme="Test",
            fact="A fact.",
            hashtags=[],
            image_prompt=None,
            status=ContentStatus.PENDING,
            created_at=dt,
            updated_at=dt,
        )
        assert resp.image_url is None


class TestPostResponse:
    """Test PostResponse API model."""

    def test_valid_creation(self):
        """Valid PostResponse with all fields."""
        dt = datetime.now(timezone.utc)
        resp = PostResponse(
            id=1,
            platform="pinterest",
            status=PostStatus.SUCCESS,
            post_url="https://pinterest.com/pin/abc",
            error=None,
            created_at=dt,
        )
        assert resp.id == 1
        assert resp.status == PostStatus.SUCCESS
        assert resp.post_url == "https://pinterest.com/pin/abc"


class TestHealthResponse:
    """Test HealthResponse API model."""

    def test_valid_creation(self):
        """Valid HealthResponse."""
        dt = datetime.now(timezone.utc)
        resp = HealthResponse(timestamp=dt)
        assert resp.status == "ok"
        assert resp.database is False
        assert resp.timestamp == dt

    def test_defaults(self):
        """Default status and database values."""
        resp = HealthResponse(timestamp=datetime.now(timezone.utc))
        assert resp.status == "ok"
        assert resp.database is False


class TestEmptyRequestModels:
    """Test empty-body request models."""

    def test_approve_request(self):
        """ApproveRequest can be instantiated with no fields."""
        req = ApproveRequest()
        assert isinstance(req, ApproveRequest)

    def test_cancel_request(self):
        """CancelRequest can be instantiated with no fields."""
        req = CancelRequest()
        assert isinstance(req, CancelRequest)

    def test_regenerate_text_request(self):
        """RegenerateTextRequest can be instantiated with no fields."""
        req = RegenerateTextRequest()
        assert isinstance(req, RegenerateTextRequest)

    def test_regenerate_image_request(self):
        """RegenerateImageRequest can be instantiated with no fields."""
        req = RegenerateImageRequest()
        assert isinstance(req, RegenerateImageRequest)


# ===================================================================
# Serialization Tests
# ===================================================================


class TestSerialization:
    """Test model_dump() and model_dump_json() round-trip."""

    def test_trend_round_trip(self):
        """Trend serializes and deserializes correctly."""
        dt = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        original = Trend(id=1, keyword="test trend", score=75.0, created_at=dt)
        data = original.model_dump()
        restored = Trend(**data)
        assert restored == original

    def test_content_option_round_trip(self):
        """ContentOption serializes and deserializes correctly."""
        dt = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        original = ContentOption(
            id=1,
            batch_id="b1",
            platform=Platform.PINTEREST,
            theme="Test Theme",
            fact="A very interesting fact.",
            hashtags=["#test"],
            status=ContentStatus.APPROVED,
            created_at=dt,
            updated_at=dt,
        )
        data = original.model_dump()
        restored = ContentOption(**data)
        assert restored == original

    def test_content_option_json_round_trip(self):
        """ContentOption serializes to JSON and back."""
        original = ContentOption(
            batch_id="b1",
            platform=Platform.INSTAGRAM,
            theme="JSON Test",
            fact="JSON round-trip works.",
        )
        json_str = original.model_dump_json()
        restored = ContentOption.model_validate_json(json_str)
        assert restored == original

    def test_health_response_round_trip(self):
        """HealthResponse serializes and deserializes correctly."""
        dt = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        original = HealthResponse(status="degraded", database=True, timestamp=dt)
        data = original.model_dump()
        restored = HealthResponse(**data)
        assert restored == original

    def test_post_json_round_trip(self):
        """Post serializes to JSON and back."""
        original = Post(
            content_option_id=1,
            platform="pinterest",
            status=PostStatus.FAILED,
            error="Something went wrong",
        )
        json_str = original.model_dump_json()
        restored = Post.model_validate_json(json_str)
        assert restored == original

    def test_enum_serializes_to_string(self):
        """Enum fields should serialize to their string values."""
        option = ContentOption(
            batch_id="b1",
            platform=Platform.PINTEREST,
            theme="Test",
            fact="A fact.",
        )
        data = option.model_dump()
        assert data["platform"] == "pinterest"
        assert data["status"] == "pending"


# ===================================================================
# Helper Function Tests
# ===================================================================


class TestHelperFunctions:
    """Test *_from_record() helper functions."""

    def test_content_option_from_record(self):
        """Convert a dict-like record to ContentOption."""
        dt = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        record = {
            "id": 1,
            "batch_id": "batch-001",
            "platform": "pinterest",
            "theme": "AI Art",
            "fact": "AI art is transforming creative industries.",
            "hashtags": ["#AI", "#art"],
            "image_prompt": "A robot painting",
            "image_path": "/images/robot.png",
            "status": "approved",
            "created_at": dt,
            "updated_at": dt,
        }
        option = content_option_from_record(record)
        assert isinstance(option, ContentOption)
        assert option.id == 1
        assert option.platform == Platform.PINTEREST
        assert option.status == ContentStatus.APPROVED
        assert option.hashtags == ["#AI", "#art"]
        assert option.image_prompt == "A robot painting"

    def test_content_option_from_record_no_hashtags(self):
        """Record with no hashtags should default to empty list."""
        record = {
            "id": 2,
            "batch_id": "b2",
            "platform": "instagram",
            "theme": "Test",
            "fact": "A fact.",
            "hashtags": None,
            "image_prompt": None,
            "image_path": None,
            "status": "pending",
            "created_at": None,
            "updated_at": None,
        }
        option = content_option_from_record(record)
        assert option.hashtags == []

    def test_trend_from_record(self):
        """Convert a dict-like record to Trend."""
        record = {
            "id": 1,
            "keyword": "machine learning",
            "score": 92.5,
            "source": "google_trends",
            "created_at": None,
        }
        trend = trend_from_record(record)
        assert isinstance(trend, Trend)
        assert trend.id == 1
        assert trend.keyword == "machine learning"
        assert trend.score == 92.5
        assert trend.source == "google_trends"

    def test_trend_from_record_default_source(self):
        """Record without source should get default."""
        record = {
            "id": 2,
            "keyword": "AI",
            "score": 80.0,
            "created_at": None,
        }
        trend = trend_from_record(record)
        assert trend.source == "google_trends"

    def test_theme_from_record(self):
        """Convert a dict-like record to Theme."""
        record = {
            "id": 1,
            "name": "AI Art Trends",
            "trend_id": 5,
            "created_at": None,
        }
        theme = theme_from_record(record)
        assert isinstance(theme, Theme)
        assert theme.id == 1
        assert theme.name == "AI Art Trends"
        assert theme.trend_id == 5

    def test_post_from_record(self):
        """Convert a dict-like record to Post."""
        dt = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
        record = {
            "id": 1,
            "content_option_id": 10,
            "platform": "pinterest",
            "image_path": "/images/post.png",
            "status": "success",
            "post_url": "https://pinterest.com/pin/abc",
            "error": None,
            "created_at": dt,
            "updated_at": dt,
        }
        post = post_from_record(record)
        assert isinstance(post, Post)
        assert post.id == 1
        assert post.content_option_id == 10
        assert post.status == PostStatus.SUCCESS
        assert post.post_url == "https://pinterest.com/pin/abc"

    def test_post_from_record_failed(self):
        """Record with FAILED status and error message."""
        record = {
            "id": 2,
            "content_option_id": 11,
            "platform": "instagram",
            "image_path": None,
            "status": "failed",
            "post_url": None,
            "error": "Rate limited",
            "created_at": None,
            "updated_at": None,
        }
        post = post_from_record(record)
        assert post.status == PostStatus.FAILED
        assert post.error == "Rate limited"
        assert post.post_url is None
