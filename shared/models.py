"""Shared Pydantic v2 data models for the Did You Know project.

Provides:
- Enums: ContentStatus, PostStatus, Platform
- Entity models: Trend, Theme, ContentOption, Post
- API request/response models: ApproveRequest, CancelRequest, etc.
- Helper functions: *_from_record() for asyncpg Record conversion
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContentStatus(str, Enum):
    """Status of a content option through its lifecycle."""

    PENDING = "pending"
    APPROVED = "approved"
    POSTED = "posted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PostStatus(str, Enum):
    """Status of a post attempt."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Platform(str, Enum):
    """Supported social media platforms."""

    PINTEREST = "pinterest"
    INSTAGRAM = "instagram"


# ---------------------------------------------------------------------------
# Entity Models
# ---------------------------------------------------------------------------


class Trend(BaseModel):
    """Represents a trending keyword from Google Trends."""

    id: Optional[int] = None
    keyword: str = Field(..., min_length=1, max_length=255)
    score: float = Field(..., ge=0.0, le=100.0)
    source: str = Field(default="google_trends", max_length=50)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Theme(BaseModel):
    """Represents a short theme name derived from a trend."""

    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    trend_id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ContentOption(BaseModel):
    """Represents a generated content option (text + image prompt + optional image).
    Each option is platform-specific — text, hashtags, and image are tailored per platform."""

    id: Optional[int] = None
    batch_id: str = Field(..., max_length=50)
    platform: Platform
    theme: str = Field(..., min_length=1, max_length=100)
    fact: str = Field(..., min_length=1)
    hashtags: list[str] = Field(default_factory=list)
    img_title: Optional[str] = None
    image_prompt: Optional[str] = None
    image_path: Optional[str] = None
    status: ContentStatus = ContentStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Post(BaseModel):
    """Represents a published post on a platform.
    Platform is inherited from the parent content_option."""

    id: Optional[int] = None
    content_option_id: int
    platform: str = Field(..., max_length=50)
    image_path: Optional[str] = None
    status: PostStatus = PostStatus.PENDING
    post_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------


class ApproveRequest(BaseModel):
    """No body needed — just the content_option_id from URL path."""


class CancelRequest(BaseModel):
    """No body needed — just the content_option_id from URL path."""


class RegenerateTextRequest(BaseModel):
    """No body needed — regenerates using existing theme."""


class RegenerateImageRequest(BaseModel):
    """No body needed — regenerates using existing image_prompt."""


class ContentOptionResponse(BaseModel):
    """API response for a single content option."""

    id: int
    batch_id: str
    platform: str
    theme: str
    fact: str
    hashtags: list[str]
    img_title: Optional[str] = None
    image_prompt: Optional[str]
    image_url: Optional[str] = None
    status: ContentStatus
    created_at: datetime
    updated_at: datetime


class PostResponse(BaseModel):
    """API response for a post."""

    id: int
    platform: str
    status: PostStatus
    post_url: Optional[str]
    error: Optional[str]
    created_at: datetime


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    database: bool = False
    timestamp: datetime


# ---------------------------------------------------------------------------
# Database record helper functions
# ---------------------------------------------------------------------------


def content_option_from_record(record: dict[str, Any]) -> ContentOption:
    """Convert a database record (asyncpg.Record or dict) to a ContentOption model."""
    return ContentOption(
        id=record["id"],
        batch_id=record["batch_id"],
        platform=record["platform"],
        theme=record["theme"],
        fact=record["fact"],
        hashtags=list(record["hashtags"]) if record.get("hashtags") else [],
        image_prompt=record.get("image_prompt"),
        img_title=record.get("img_title"),
        image_path=record.get("image_path"),
        status=record["status"],
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )


def trend_from_record(record: dict[str, Any]) -> Trend:
    """Convert a database record (asyncpg.Record or dict) to a Trend model."""
    return Trend(
        id=record["id"],
        keyword=record["keyword"],
        score=record["score"],
        source=record.get("source", "google_trends"),
        created_at=record.get("created_at"),
    )


def theme_from_record(record: dict[str, Any]) -> Theme:
    """Convert a database record (asyncpg.Record or dict) to a Theme model."""
    return Theme(
        id=record["id"],
        name=record["name"],
        trend_id=record["trend_id"],
        created_at=record.get("created_at"),
    )


def post_from_record(record: dict[str, Any]) -> Post:
    """Convert a database record (asyncpg.Record or dict) to a Post model."""
    return Post(
        id=record["id"],
        content_option_id=record["content_option_id"],
        platform=record["platform"],
        image_path=record.get("image_path"),
        status=record["status"],
        post_url=record.get("post_url"),
        error=record.get("error"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
    )