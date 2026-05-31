# Module 3: Content Generator

## 1. Feature Overview
**Purpose**: Generate multiple platform-specific content options (fact + hashtags + image prompt) from a theme using AI
**Business Value**: Creates the core content that becomes social media posts, tailored per platform
**Scope**: For each enabled platform, check queue limits, generate N text variations using platform-specific constraints, generate image prompt for each, save to DB
**Success Criteria**: N content options per platform saved with status `pending`, queue limit respected, old options expired

## 2. Service Ownership
**Primary Service**: `modules/content_generator.py`
**Dependent Services**: Module 2 (produces themes), Module 4 (uses image prompts), `shared/openrouter_client.py`, `shared/db.py`
**Interface Changes**: Reads from `themes` table, writes to `content_options` table (with `platform` field)

## 3. Detailed Implementation

### File Location
`modules/content_generator.py`

### Class Interface

```python
class ContentGenerator:
    """Generates platform-specific content options from themes."""

    def __init__(self, db_pool, openrouter_client, config: dict):
        """
        Args:
            db_pool: asyncpg connection pool
            openrouter_client: OpenRouterClient instance
            config: content_template.yaml config dict
        """

    async def run(self, theme: Theme, platforms: list[str]) -> list[ContentOption]:
        """
        Generate content options for a theme, for each platform.

        Args:
            theme: Theme to generate content for
            platforms: List of platform names to generate for (e.g., ["pinterest", "instagram"])

        Process:
        1. Check queue size — if >= max_pending, log and return empty list
        2. Expire old pending options (older than expire_days)
        3. For each platform:
           a. Load platform-specific constraints (char limit, hashtag count) from config
           b. Generate N text variations (fact + hashtags) via OpenRouter, constrained to platform limits
           c. For each text variation, generate image prompt via OpenRouter
           d. Save all options to content_options table with platform field
        4. Return combined list of all saved ContentOption models
        """

    async def _check_queue(self) -> int:
        """Count pending options. Returns count."""

    async def _expire_old_options(self, days: int) -> int:
        """Update status of old pending options to 'expired'.
        Returns count of expired options."""

    async def _generate_text_variations(self, theme: str, count: int, platform_limits: dict) -> list[dict]:
        """Generate N text variations (fact + hashtags) for a theme, respecting platform limits.
        Args:
            theme: Theme name
            count: Number of variations
            platform_limits: {"character_limit": 500, "hashtag_count": "5-10"}
        Returns list of {"fact": str, "hashtags": list[str]}."""

    async def _generate_image_prompt(self, fact: str) -> str:
        """Generate an image prompt from a fact.
        Returns image description string."""

    async def _save_options(self, theme: str, batch_id: str, platform: str, options: list[dict]) -> list[ContentOption]:
        """Batch INSERT into content_options table with platform field.
        Returns list of saved ContentOption models."""
```

### Queue Management

**Check before generation**:
```sql
SELECT COUNT(*) FROM content_options WHERE status = 'pending';
```
If count >= `max_pending` (from config), skip generation entirely.

**Expire old options**:
```sql
UPDATE content_options
SET status = 'expired', updated_at = CURRENT_TIMESTAMP
WHERE status = 'pending'
AND created_at < NOW() - INTERVAL '7 days';
```
Only runs if `cleanup_on_generate` is true in config.

### AI Prompt Flow

**Platform-specific constraints** (from `config/content_template.yaml`):
```python
# Example: Pinterest constraints
platform_limits = {
    "character_limit": 500,
    "hashtag_count": "5-10"
}
# These are injected into the prompt so the AI generates platform-appropriate content
```

**Step 1 — Text Generation**:
- Model: configurable (default `openai/gpt-4o-mini`)
- Prompt: `text_prompt` from config, formatted with `{theme}` + platform constraints appended
- Response format: `{"type": "json_object"}` to enforce JSON
- Expected response:
```json
{
    "fact": "Air fryers use rapid air technology to create crispy food with up to 80% less oil.",
    "hashtags": ["#AirFryer", "#HealthyCooking", "#CrispyFood", "#LowOil", "#KitchenHacks"]
}
```
- Pinterest: fact targets ~400 chars + 5-10 hashtags (fits 500 char limit)
- Instagram: fact can be longer + 10-30 hashtags (fits 2200 char limit)

**Step 2 — Image Prompt Generation** (for each text variation):
- Model: configurable (default `openai/gpt-4o-mini`)
- Prompt: `image_prompt` from config, formatted with `{fact}`
- Response: plain text (2-3 sentences)
- Example:
```
A warm overhead shot of golden crispy chicken wings fresh from an air fryer,
surrounded by colorful dipping sauces and fresh herbs on a rustic wooden
cutting board, bathed in bright natural window light.
```

### Batch ID Generation

```python
import uuid
batch_id = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
```

### Database Operations

```sql
-- Batch insert content options (now includes platform)
INSERT INTO content_options (batch_id, platform, theme, fact, hashtags, image_prompt, status, created_at)
VALUES ($1, $2, $3, $4, $5, $6, 'pending', CURRENT_TIMESTAMP)
RETURNING id, batch_id, platform, theme, fact, hashtags, image_prompt, image_path, status, created_at, updated_at;
```

**Note**: `hashtags` stored as JSON array in JSONB column. `image_path` is NULL at this stage (Module 4 fills it). Each option is tagged with its target platform.

## 4. Error Handling
**Expected Failures**:
- Queue full (>= max_pending)
- OpenRouter API error during text generation
- AI returns invalid JSON
- AI returns fewer variations than requested
- Database insert failure

**Recovery Strategies**:
- Queue full: Log info, return empty list (not an error)
- API error: Retry once, then raise
- Invalid JSON: Parse response manually (regex for fact/hashtags), retry if fails
- Fewer variations: Use what was returned, log warning
- DB failure: Log and re-raise

**Logging Requirements**:
- INFO: Generation started, N options created, queue full skip
- WARNING: Fewer variations than expected, JSON parse retry
- ERROR: API failure, DB failure

## 5. Input/Output Specifications
**Input**:
```python
theme = Theme(name="Crispy Cooking", trend_id=1)
platforms = ["pinterest", "instagram"]  # from config, filtered by enabled
```

**Output**:
```python
[
    ContentOption(
        id=1,
        batch_id="batch_20240115_100000_abc123",
        platform="pinterest",
        theme="Crispy Cooking",
        fact="Air fryers use rapid air technology...",
        hashtags=["#AirFryer", "#HealthyCooking", ...],  # 5-10 hashtags
        image_prompt="A warm overhead shot of...",
        image_path=None,
        status=ContentStatus.PENDING,
        created_at=datetime(...),
        updated_at=datetime(...)
    ),
    ContentOption(
        id=2,
        batch_id="batch_20240115_100000_abc123",
        platform="instagram",
        theme="Crispy Cooking",
        fact="Air fryers use rapid air technology to create crispy food with up to 80% less oil. Perfect for health-conscious food lovers who don't want to sacrifice flavor.",
        hashtags=["#AirFryer", "#HealthyCooking", "#CrispyFood", ...],  # 10-30 hashtags
        image_prompt="A warm overhead shot of...",
        image_path=None,
        status=ContentStatus.PENDING,
        created_at=datetime(...),
        updated_at=datetime(...)
    ),
    # ... N more options per platform
]
```

**Validation**:
- `platform`: must be valid Platform enum value
- `fact`: non-empty string, length respects platform character_limit
- `hashtags`: list of strings, count respects platform hashtag_count
- `image_prompt`: non-empty string
- `batch_id`: matches pattern `batch_YYYYMMDD_HHMMSS_xxxxxx`

## 6. Edge Cases
- Queue at exactly `max_pending` (should skip)
- AI returns empty fact or empty hashtags
- AI returns hashtags without `#` prefix (auto-prepend)
- Theme has special characters that break prompt formatting
- Concurrent generation runs (APScheduler `max_instances=1` prevents this)
- One platform succeeds, another fails (partial results saved)
- Platform character limit very small (fact truncated or regenerated)

## 7. Dependencies
- `shared/openrouter_client.py` (text generation)
- `shared/db.py` (database access)
- `shared/config_loader.py` (prompt templates, queue config)
- OpenRouter API key

## 8. Testing Requirements
- **Unit tests**: Mock OpenRouter, test prompt formatting, test JSON parsing
- **Queue tests**: Test max_pending check, test expiry logic
- **Integration tests**: Full generation with test database
- **Edge case tests**: Invalid JSON, empty response, queue full

## 9. Deployment Considerations
- **Migration**: None (uses existing content_options table)
- **Rollback**: N/A
- **Monitoring**: Log generation count, queue size, expiry count
- **Performance**: Per platform: N AI calls (text) + N AI calls (image prompt) = 2N calls. For 2 platforms × 3 variants = 12 AI calls, ~60s total
