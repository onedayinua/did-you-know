# Shared Pydantic Models

## 1. Feature Overview
**Purpose**: Define shared data models for all entities in the system using Pydantic v2
**Business Value**: Type-safe data exchange between modules, automatic validation, serialization
**Scope**: Models for Trend, Theme, ContentOption, Post, plus request/response models for API endpoints
**Success Criteria**: All models validate correctly, serialize to/from JSON and database records

## 2. Service Ownership
**Primary Service**: `shared/models.py`
**Dependent Services**: All modules use these models for data exchange
**Interface Changes**: New shared types (no external API changes)

## 3. Detailed Implementation

### File Location
`shared/models.py`

### Entity Models

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class ContentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    POSTED = "posted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PostStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class Platform(str, Enum):
    PINTEREST = "pinterest"
    INSTAGRAM = "instagram"


class Trend(BaseModel):
    """Represents a trending keyword from Google Trends."""
    id: Optional[int] = None
    keyword: str = Field(..., min_length=1, max_length=255)
    score: float = Field(..., ge=0.0, le=100.0)
    source: str = Field(default="google_trends", max_length=50)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Theme(BaseModel):
    """Represents a short theme name derived from a trend."""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100)
    trend_id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContentOption(BaseModel):
    """Represents a generated content option (text + image prompt + optional image).
    Each option is platform-specific — text, hashtags, and image are tailored per platform."""
    id: Optional[int] = None
    batch_id: str = Field(..., max_length=50)
    platform: Platform
    theme: str = Field(..., min_length=1, max_length=100)
    fact: str = Field(..., min_length=1)
    hashtags: list[str] = Field(default_factory=list)
    image_prompt: Optional[str] = None
    image_path: Optional[str] = None
    status: ContentStatus = ContentStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True
```

### API Request/Response Models

```python
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
    image_prompt: Optional[str]
    image_url: Optional[str] = None  # URL to access image via API
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
```

### Helper Methods

```python
def content_option_from_record(record: asyncpg.Record) -> ContentOption:
    """Convert a database record to a ContentOption model."""

def trend_from_record(record: asyncpg.Record) -> Trend:
    """Convert a database record to a Trend model."""

def theme_from_record(record: asyncpg.Record) -> Theme:
    """Convert a database record to a Theme model."""

def post_from_record(record: asyncpg.Record) -> Post:
    """Convert a database record to a Post model."""
```

## 4. Error Handling
**Expected Failures**:
- Invalid field values (too long, wrong type)
- Missing required fields
- Invalid enum values

**Recovery Strategies**:
- Pydantic raises `ValidationError` with field-level detail
- API layer catches `ValidationError` and returns 422 with details
- Database layer validates before INSERT/UPDATE

**Logging Requirements**:
- DEBUG: Model validation failures (for development)

## 5. Input/Output Specifications
**Input Validation** (enforced by Pydantic):
- `keyword`: 1-255 characters
- `score`: 0.0-100.0
- `name` (theme): 1-100 characters, max 3 words (validated in Module 2, not model)
- `trend_id` (theme): positive integer, FK to trends.id
- `fact`: non-empty string
- `hashtags`: list of strings
- `status`: must be valid enum value
- `platform`: 1-50 characters

**Output Formats**: JSON-serializable via `model.model_dump()` or `model.model_dump_json()`

## 6. Edge Cases
- Empty hashtags list (valid — defaults to `[]`)
- None values for optional fields (image_prompt, image_path, post_url)
- Unicode characters in fact/keyword
- Very long fact text (no explicit max, limited by TEXT column)

## 7. Dependencies
- `pydantic` v2+
- `asyncpg` (for Record type hints in helper methods)

## 8. Testing Requirements
- **Unit tests**: Validate each model with valid and invalid data
- **Serialization tests**: Round-trip JSON → Model → JSON
- **Enum tests**: Verify all status enum values
- **Edge case tests**: Empty strings, boundary values, None handling

## 9. Deployment Considerations
- **Migration**: None
- **Rollback**: N/A
- **Monitoring**: N/A
- **Performance**: Pydantic validation is negligible overhead
