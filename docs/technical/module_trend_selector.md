# Module 1: Trend Selector

## 1. Feature Overview
**Purpose**: Identify trending culinary topics from Google Trends and save the best unused trend to the database
**Business Value**: Provides fresh, relevant topics for content creation pipeline
**Scope**: Fetch trends via `pytrends`, filter for food relevance, deduplicate against DB, save best trend
**Success Criteria**: One trend saved per execution, no duplicates within `trend_history_days`, falls back gracefully on API failure

## 2. Service Ownership
**Primary Service**: `modules/trend_selector.py`
**Dependent Services**: Module 2 (reads trends), `shared/db.py`, `shared/config_loader.py`
**Interface Changes**: Writes to `trends` table

## 3. Detailed Implementation

### File Location
`modules/trend_selector.py`

### Class Interface

```python
class TrendSelector:
    """Selects trending topics from Google Trends."""

    def __init__(self, db_pool, config: dict):
        """
        Args:
            db_pool: asyncpg connection pool
            config: backup_trends.yaml config dict
        """

    async def run(self) -> Trend | None:
        """
        Main execution method. Returns the selected Trend or None if no trend found.

        Process:
        1. Fetch trending searches via pytrends
        2. Filter for food-related keywords
        3. Query DB for recently used keywords (within trend_history_days)
        4. Select highest-scoring unused keyword
        5. Save to trends table
        6. Return saved Trend model
        """

    async def _fetch_trends(self) -> list[dict]:
        """Fetch trending searches from Google Trends API.
        Returns list of {"keyword": str, "score": float}."""

    async def _get_used_keywords(self, days: int) -> set[str]:
        """Query trends table for keywords used in last N days."""

    async def _select_best(self, candidates: list[dict], used: set[str]) -> dict | None:
        """Select highest-scoring unused trend. Returns None if all used."""

    async def _save_trend(self, keyword: str, score: float, source: str) -> Trend:
        """INSERT into trends table and return Trend model."""

    async def _use_backup(self) -> Trend | None:
        """Use backup trend from config when API fails."""
```

### Google Trends Integration

**Library**: `pytrends` (unofficial API wrapper)

**Process**:
```python
from pytrends.request import TrendReq

pytrends = TrendReq(hl='en-US', tz=360)
pytrends.build_payload(kw_list=[], cat='71')  # cat 71 = Food & Drink
trending = pytrends.trending_searches(pn='united_states')
```

**Fallback chain**:
1. Try `pytrends.trending_searches()` for real-time trending
2. If that fails, try `pytrends.get_historical_interest()` for recent food terms
3. If that fails, use `backup_trends.yaml` list
4. If backup empty, return None

### Deduplication Logic

```sql
-- Get recently used keywords
SELECT keyword FROM trends
WHERE created_at > NOW() - INTERVAL '{trend_history_days} days'
```

**Selection algorithm**:
1. Filter candidates: remove any keyword already in used set
2. Sort remaining by score descending
3. Pick first (highest score)
4. If no unused candidates: pick highest-scoring overall (fallback #2)
5. If still none: use backup trends from config

### Database Operations

```sql
-- Insert new trend
INSERT INTO trends (keyword, score, source, created_at)
VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
RETURNING id, keyword, score, source, created_at;
```

## 4. Error Handling
**Expected Failures**:
- `pytrends` network timeout (30s)
- `pytrends` rate limiting (Google blocks)
- Database connection failure
- All trends already used (deduplication exhaustion)

**Recovery Strategies**:
- Network timeout: Retry once, then use backup trends
- Rate limiting: Use backup trends immediately
- DB failure: Log error, re-raise (caller handles)
- All used: Fall back to re-using highest-scoring trend

**Logging Requirements**:
- INFO: Trend selected, trend saved, fallback used
- WARNING: API failure, using backup
- ERROR: All fallbacks exhausted

## 5. Input/Output Specifications
**Input**: None (reads from API + DB)
**Output**:
```python
Trend(
    id=1,
    keyword="air fryer recipes",
    score=92.5,
    source="google_trends",
    created_at=datetime(2024, 1, 15, 10, 0, 0)
)
```

**Validation**:
- `keyword`: non-empty, max 255 chars
- `score`: 0.0-100.0

## 6. Edge Cases
- Google Trends returns empty list
- All backup trends already used
- `pytrends` returns non-food trending topics (e.g., celebrity news)
- Duplicate keyword with different score
- Very long keyword strings (> 255 chars)

## 7. Dependencies
- `pytrends` library
- `shared/db.py` (database access)
- `shared/config_loader.py` (backup trends config)

## 8. Testing Requirements
- **Unit tests**: Mock pytrends, test selection logic, test deduplication
- **Integration tests**: Full run with test database
- **Fallback tests**: Verify backup trends used on API failure
- **Edge case tests**: Empty trends, all used, timeout

## 9. Deployment Considerations
- **Migration**: None (uses existing trends table)
- **Rollback**: N/A
- **Monitoring**: Log trend selection count, API success rate
- **Performance**: Single API call + single DB write, < 5s
