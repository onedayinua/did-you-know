# Module 2: Theme Associator

## 1. Feature Overview
**Purpose**: Create a short, memorable theme name (up to 3 words) from a trend keyword using AI
**Business Value**: Transforms raw trends into content-ready themes that fit the "Did you know that ___?" format
**Scope**: Read trend from DB, call OpenRouter for association, deduplicate against recent themes, save to DB
**Success Criteria**: Theme saved to DB, max 3 words, not duplicated within `min_hours_between_similar`

## 2. Service Ownership
**Primary Service**: `modules/theme_associator.py`
**Dependent Services**: Module 1 (produces trends), Module 3 (reads themes), `shared/openrouter_client.py`, `shared/db.py`
**Interface Changes**: Reads from `trends` table, writes to `themes` table

## 3. Detailed Implementation

### File Location
`modules/theme_associator.py`

### Class Interface

```python
class ThemeAssociator:
    """Creates theme names from trending keywords."""

    def __init__(self, db_pool, openrouter_client, config: dict):
        """
        Args:
            db_pool: asyncpg connection pool
            openrouter_client: OpenRouterClient instance
            config: content_template.yaml config dict
        """

    async def run(self, trend: Trend) -> Theme:
        """
        Create a theme from a trend.

        Process:
        1. Load theme_prompt template from config
        2. Format prompt with trend keyword
        3. Call OpenRouter for text generation
        4. Parse response (extract theme name)
        5. Check deduplication against recent themes
        6. If duplicate, request alternative from OpenRouter (max 2 retries)
        7. Save theme to themes table
        8. Return saved Theme model
        """

    async def _generate_theme(self, keyword: str) -> str:
        """Call OpenRouter to generate theme name from keyword.
        Returns raw theme name string."""

    async def _is_duplicate(self, theme_name: str, hours: int) -> bool:
        """Check if theme name is too similar to recently used themes.
        Uses ILIKE for fuzzy matching."""

    async def _save_theme(self, name: str, trend_id: int) -> Theme:
        """INSERT into themes table and return Theme model."""
```

### AI Prompt Format

**System message** (implied by prompt template):
```
You are a creative culinary content strategist.
```

**User message** (from `config/content_template.yaml` → `theme_prompt`):
```
Given the trend 'air fryer recipes', find associations: related cooking concepts,
ingredients, cultural angles, or health connections. Based on these
associations, create a short theme name (up to 3 words) that fits
naturally into: 'Did you know that {theme}?'

Return ONLY the theme name, nothing else. Example: "Crispy Cooking"
```

**Expected response**: `Crispy Cooking` (plain text, no JSON)

### Deduplication Logic

```sql
-- Check for similar themes in last N hours
SELECT name FROM themes
WHERE created_at > NOW() - INTERVAL '12 hours'
AND (
    name ILIKE $1           -- exact match
    OR name ILIKE '%' || $1 || '%'  -- contains
    OR $1 ILIKE '%' || name || '%'  -- is contained by
)
```

**Similarity check**: Case-insensitive substring match (not Levenshtein — keep it simple for MVP)

**Retry flow**:
1. Generate theme → check dedup
2. If duplicate: prompt OpenRouter "That theme was used recently. Suggest a different one for 'air fryer recipes'"
3. Check dedup again
4. If still duplicate: accept it (log warning)

### Database Operations

```sql
-- Insert new theme
INSERT INTO themes (name, trend_id, created_at)
VALUES ($1, $2, CURRENT_TIMESTAMP)
RETURNING id, name, trend_id, created_at;
```

## 4. Error Handling
**Expected Failures**:
- OpenRouter API error/timeout
- AI returns theme with > 3 words
- AI returns empty response
- Database write failure

**Recovery Strategies**:
- API error: Retry once, then raise
- Too many words: Truncate to first 3 words, log warning
- Empty response: Retry once with explicit "return a theme name" emphasis
- DB failure: Log and re-raise

**Logging Requirements**:
- INFO: Theme generated, theme saved
- WARNING: Dedup retry, theme truncated
- ERROR: API failure, DB failure

## 5. Input/Output Specifications
**Input**:
```python
Trend(keyword="air fryer recipes", score=92.5, ...)
```

**Output**:
```python
Theme(id=1, name="Crispy Cooking", trend_id=1, created_at=...)
```

**Validation**:
- `name`: 1-100 chars, max 3 words (enforced by prompt + post-processing)

## 6. Edge Cases
- AI returns theme with punctuation or quotes
- AI returns full sentence instead of short theme
- Theme exactly matches one from 13 hours ago (just outside window)
- Multiple themes with same name but different trends
- Unicode characters in theme name

## 7. Dependencies
- `shared/openrouter_client.py` (text generation)
- `shared/db.py` (database access)
- `shared/config_loader.py` (prompt templates)
- OpenRouter API key

## 8. Testing Requirements
- **Unit tests**: Mock OpenRouter, test prompt formatting, test word count validation
- **Dedup tests**: Test similarity matching with various inputs
- **Integration tests**: Full flow with test database
- **Edge case tests**: Empty response, too-long response, special characters

## 9. Deployment Considerations
- **Migration**: None (uses existing themes table)
- **Rollback**: N/A
- **Monitoring**: Log generation latency, dedup retry count
- **Performance**: Single AI call + single DB write, < 10s
