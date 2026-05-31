# Module 6: Platform Poster

## 1. Feature Overview
**Purpose**: Post approved content with images to the target platform specified on the content option
**Business Value**: Automates the final step of publishing content to Pinterest, Instagram, etc.
**Scope**: Read approved content option (which already has platform + platform-specific content), upload image + create post via platform API, update DB status
**Success Criteria**: Post published with URL saved, or error recorded in DB

## 2. Service Ownership
**Primary Service**: `modules/platform_poster.py`
**Dependent Services**: Module 5 (triggers on approval), `shared/db.py`, platform APIs (Pinterest, Instagram)
**Interface Changes**: Reads from `content_options` table (platform is on the option), writes to `posts` table

## 3. Detailed Implementation

### File Location
`modules/platform_poster.py`

### Class Interface

```python
class PlatformPoster:
    """Posts approved content to the target platform."""

    def __init__(self, db_pool, config: dict):
        """
        Args:
            db_pool: asyncpg connection pool
            config: platforms.yaml config dict
        """

    async def run(self, content_option_id: int) -> Post:
        """
        Post approved content to its target platform.

        Process:
        1. Load content option from DB (verify status = 'approved')
        2. Platform is already on the option — no iteration needed
        3. Format content for the option's platform (content already tailored, just assemble)
        4. Create post entry in posts table (status = 'pending')
        5. Upload image + create post via platform API
        6. Update post status (success/failed) and URL
        7. Update content_option status to 'posted' on success
        8. Return Post model
        """

    async def _format_for_posting(self, option: ContentOption) -> dict:
        """Assemble final post payload from option.
        Content is already platform-specific (text length, hashtag count).
        Just combine fact + hashtags into caption.
        Returns {"caption": str, "title": str, "image_path": str}."""

    async def _post_to_pinterest(self, content: dict, config: dict) -> dict:
        """Post to Pinterest API.
        Returns {"post_url": str} or raises."""

    async def _post_to_instagram(self, content: dict, config: dict) -> dict:
        """Post to Instagram API (stub for MVP).
        Returns {"post_url": str} or raises."""

    async def _create_post_record(self, content_option_id: int, platform: str, image_path: str) -> Post:
        """INSERT into posts table."""

    async def _update_post_result(self, post_id: int, status: str, url: str = None, error: str = None) -> None:
        """UPDATE posts table with result."""
```

### Platform Formatting

Since content is already generated per-platform by Module 3, formatting at posting time is minimal — just assembling the final caption from pre-sized components.

**Pinterest**:
```python
def _format_for_posting(self, option):
    # Content already fits Pinterest limits (500 chars, 5-10 hashtags)
    # Just assemble caption
    hashtags = option.hashtags
    hashtag_str = " ".join(hashtags)
    caption = f"{option.fact}\n\n{hashtag_str}"

    return {
        "caption": caption,
        "title": option.theme,  # Pin title
        "image_path": option.image_path,
        "board_id": config["platforms"]["pinterest"]["board_id"]
    }
```

**Instagram** (stub for MVP):
```python
def _format_for_posting(self, option):
    # Content already fits Instagram limits (2200 chars, 10-30 hashtags)
    hashtags = option.hashtags
    hashtag_str = " ".join(hashtags)
    caption = f"{option.fact}\n\n.\n.\n.\n{hashtag_str}"

    return {
        "caption": caption,
        "image_path": option.image_path
    }
```

**Platform dispatch**:
```python
POST_HANDLERS = {
    "pinterest": "_post_to_pinterest",
    "instagram": "_post_to_instagram",
}

async def run(self, content_option_id: int) -> Post:
    option = await self._load_option(content_option_id)
    handler = getattr(self, POST_HANDLERS[option.platform])
    # ... call handler
```

### Pinterest API Integration

**Endpoint**: `POST https://api.pinterest.com/v5/pins`

**Request**:
```python
async with httpx.AsyncClient() as client:
    # Upload image first (if needed)
    # Create pin
    response = await client.post(
        f"{config['api_base']}/pins",
        headers={"Authorization": f"Bearer {config['access_token']}"},
        json={
            "board_id": config["board_id"],
            "title": content["title"],
            "description": content["caption"],
            "media_source": {
                "source_type": "image_url",
                "url": content["image_url"]  # or upload binary
            }
        },
        timeout=30.0
    )
```

**Response**:
```json
{
    "id": "pin_id",
    "url": "https://pinterest.com/pin/..."
}
```

### Database Operations

```sql
-- Create post record
INSERT INTO posts (content_option_id, platform, image_path, status, created_at)
VALUES ($1, $2, $3, 'pending', CURRENT_TIMESTAMP)
RETURNING id, content_option_id, platform, image_path, status, created_at;

-- Update post with result
UPDATE posts
SET status = $1, post_url = $2, error = $3, updated_at = CURRENT_TIMESTAMP
WHERE id = $4;

-- Update content option status
UPDATE content_options
SET status = 'posted', updated_at = CURRENT_TIMESTAMP
WHERE id = $1;
```

## 4. Error Handling
**Expected Failures**:
- Platform API returns error (4xx, 5xx)
- Image upload fails
- Platform API rate limiting
- Network timeout
- Content option not in 'approved' status
- Platform not enabled in config

**Recovery Strategies**:
- API error: Record error in `posts` table, mark as 'failed'
- Upload fail: Retry once, then mark as 'failed'
- Rate limiting: Wait and retry once (30s)
- Timeout: Mark as 'failed' with timeout message
- Wrong status: Return error to caller
- Platform disabled: Skip silently

**Logging Requirements**:
- INFO: Post started, post successful (with URL), post failed
- WARNING: Retry, platform skipped
- ERROR: All platforms failed for content option

## 5. Input/Output Specifications
**Input**:
```python
content_option_id: int  # ID of approved content option (platform is on the option)
```

**Output**:
```python
Post(
    id=1,
    content_option_id=5,
    platform="pinterest",  # copied from content_option.platform
    image_path="data/images/batch_..._5.png",
    status=PostStatus.SUCCESS,
    post_url="https://pinterest.com/pin/...",
    error=None,
    created_at=datetime(...),
    updated_at=datetime(...)
)
```

## 6. Edge Cases
- Content option has no image (image_path is NULL)
- Platform API returns error
- Platform config missing required fields (board_id, access_token)
- Image file deleted from disk before posting
- Content option already posted (duplicate approval)
- Platform handler not implemented (e.g., instagram stub)

## 7. Dependencies
- `httpx` for async HTTP to platform APIs
- `shared/db.py` (database access)
- `shared/config_loader.py` (platform config)
- Platform API credentials (env vars)

## 8. Testing Requirements
- **Unit tests**: Mock platform APIs, test formatting, test error handling
- **Integration tests**: Full posting flow with test database
- **Platform tests**: Test each platform formatter separately
- **Error tests**: API failure, timeout, rate limiting

## 9. Deployment Considerations
- **Migration**: None (uses existing posts table)
- **Rollback**: N/A
- **Monitoring**: Log post success/failure rate per platform
- **Performance**: Sequential posting to avoid rate limits, ~15s per platform
- **Security**: API keys in environment variables, never logged
