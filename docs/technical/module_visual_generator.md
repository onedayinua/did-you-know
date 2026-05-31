# Module 4: Visual Generator

## 1. Feature Overview
**Purpose**: Generate images for content options using AI image generation with platform-specific dimensions
**Business Value**: Provides visual assets sized correctly for each platform (portrait for Pinterest, square for Instagram)
**Scope**: Read content options with image prompts, determine dimensions from option's platform, call OpenRouter image generation, save images to `data/images/`, update DB
**Success Criteria**: Image saved to disk in correct dimensions, `image_path` updated in `content_options` table

## 2. Service Ownership
**Primary Service**: `modules/visual_generator.py`
**Dependent Services**: Module 3 (produces image prompts), Module 5 (displays images), `shared/openrouter_client.py`, `shared/db.py`
**Interface Changes**: Updates `content_options.image_path`, creates files in `data/images/`

## 3. Detailed Implementation

### File Location
`modules/visual_generator.py`

### Class Interface

```python
class VisualGenerator:
    """Generates images for content options."""

    def __init__(self, db_pool, openrouter_client, config: dict):
        """
        Args:
            db_pool: asyncpg connection pool
            openrouter_client: OpenRouterClient instance
            config: platforms.yaml config dict
        """

    async def run(self, content_option_ids: list[int] | None = None) -> list[ContentOption]:
        """
        Generate images for content options.

        Args:
            content_option_ids: Specific option IDs to process, or None for all pending without images

        Process:
        1. Query content_options for options with image_prompt but no image_path
        2. For each option:
           a. Call OpenRouter image generation with image_prompt
           b. Save image bytes to data/images/{batch_id}_{option_id}.png
           c. Update content_options.image_path
        3. Return updated ContentOption models
        """

    async def _get_pending_options(self, ids: list[int] | None) -> list[ContentOption]:
        """Query for options needing image generation."""

    async def _generate_and_save(self, option: ContentOption, dimensions: dict) -> str:
        """
        Generate image and save to disk.

        Args:
            option: ContentOption with image_prompt
            dimensions: {"width": 1000, "height": 1500}

        Returns:
            File path relative to project root
        """

    async def _update_image_path(self, option_id: int, image_path: str) -> None:
        """UPDATE content_options SET image_path = $1 WHERE id = $2"""
```

### Image Generation Flow

**Query for pending images** (platform is on the option):
```sql
SELECT id, batch_id, platform, image_prompt
FROM content_options
WHERE image_prompt IS NOT NULL
AND image_path IS NULL
AND status = 'pending'
ORDER BY created_at ASC;
```

**Or for specific IDs**:
```sql
SELECT id, batch_id, platform, image_prompt
FROM content_options
WHERE id = ANY($1)
AND image_prompt IS NOT NULL
AND status = 'pending';
```

**Image dimensions** (from `config/platforms.yaml`, selected by `option.platform`):
```python
# Dimension mapping per platform
PLATFORM_DIMENSIONS = {
    "pinterest": {"width": 1000, "height": 1500},  # portrait, pin format
    "instagram": {"width": 1080, "height": 1080},  # square
}

# Look up dimensions from option.platform
dimensions = PLATFORM_DIMENSIONS[option.platform]
```

**Image size string for API** (mapped to DALL-E supported sizes):
```python
# OpenRouter/DALL-E accepts: "1024x1024", "1024x1792", "1792x1024"
DALLE_SIZE_MAP = {
    "pinterest": "1024x1792",  # closest to 1000x1500
    "instagram": "1024x1024",  # exact match for 1080x1080
}
size = DALLE_SIZE_MAP[option.platform]
```

### File Storage

**Path pattern**: `data/images/{batch_id}_{option_id}.png`

**Directory creation**:
```python
import os
os.makedirs("data/images", exist_ok=True)
```

**File naming**:
```python
filename = f"{option.batch_id}_{option.id}.png"
filepath = f"data/images/{filename}"
```

### Database Update

```sql
UPDATE content_options
SET image_path = $1, updated_at = CURRENT_TIMESTAMP
WHERE id = $2;
```

## 4. Error Handling
**Expected Failures**:
- OpenRouter image generation API error
- Image download fails (network error)
- Disk write fails (permissions, full disk)
- Invalid image format returned
- No pending options to process

**Recovery Strategies**:
- API error: Retry once with 5s delay, then skip option (log error)
- Download fail: Retry once, then skip option
- Disk fail: Log error with path, re-raise (critical)
- Invalid format: Log error, skip option
- No pending: Log info, return empty list (not an error)

**Logging Requirements**:
- INFO: Image generated, image saved, N images processed
- WARNING: Image generation retry, option skipped
- ERROR: API failure, disk failure

## 5. Input/Output Specifications
**Input**: List of content_option_ids or None (process all pending)
**Output**:
```python
[
    ContentOption(
        id=1,
        batch_id="batch_20240115_100000_abc123",
        image_path="data/images/batch_20240115_100000_abc123_1.png",
        # ... other fields
    )
]
```

**Validation**:
- Image file must be valid PNG
- Image path must be relative (no absolute paths)

## 6. Edge Cases
- Option has `image_prompt` but `status != 'pending'` (skip)
- Concurrent calls for same option (process once, skip duplicates)
- Image generation returns different format than expected
- Very large image files (> 10MB)
- Partial write (image saved but DB update fails)

## 7. Dependencies
- `shared/openrouter_client.py` (image generation)
- `shared/db.py` (database access)
- `shared/config_loader.py` (platform config for dimensions)
- OpenRouter API key
- `data/images/` directory (created on first run)

## 8. Testing Requirements
- **Unit tests**: Mock OpenRouter, test file naming, test dimension mapping
- **Integration tests**: Full generation with test database + temp directory
- **File system tests**: Verify image saved correctly, verify path in DB
- **Error tests**: API failure, disk failure, partial write

## 9. Deployment Considerations
- **Migration**: Ensure `data/images/` directory exists and is writable
- **Rollback**: N/A
- **Monitoring**: Log image generation count, file sizes, API latency
- **Performance**: One API call per image, ~15s each; process sequentially to avoid rate limits
- **Storage**: Plan for image storage growth (~1MB per image, ~30 images/week)
