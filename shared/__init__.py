"""
did-you-know shared utilities.

Provides:
- config_loader: YAML config loading with env var substitution
- db: async PostgreSQL connection pool with query helpers
- models: Pydantic v2 data models for entities, API, and database records
"""

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

__all__ = [
    # Enums
    "ContentStatus",
    "PostStatus",
    "Platform",
    # Entity models
    "Trend",
    "Theme",
    "ContentOption",
    "Post",
    # API request models
    "ApproveRequest",
    "CancelRequest",
    "RegenerateTextRequest",
    "RegenerateImageRequest",
    # API response models
    "ContentOptionResponse",
    "PostResponse",
    "HealthResponse",
    # Helper functions
    "content_option_from_record",
    "trend_from_record",
    "theme_from_record",
    "post_from_record",
]