# trend_selector_replace_pytrends_with_rss.md

## 1. Feature Overview
**Purpose**: Replace the dead `pytrends` library (archived April 2025, last release April 2023) with direct HTTP calls to Google Trends RSS feed, which is a live, working endpoint.
**Business Value**: The pipeline currently fails to fetch any trends because all pytrends API endpoints return 404 or 429 errors. The RSS feed at `https://trends.google.com/trending/rss?geo=US` works and returns real-time trending data.
**Scope**: 
- Remove pytrends dependency entirely
- Replace with direct RSS feed parsing using `xml.etree.ElementTree` (stdlib, no extra deps)
- Keep the same fallback chain structure but with working endpoints
- Keep backup trends as final fallback
**Success Criteria**: `python main.py generate` successfully fetches real trends from Google and produces content.

## 2. Service Ownership
**Primary Service**: `modules/trend_selector.py` (TrendSelector class)
**Dependent Services**: None
**Interface Changes**: 
- Remove `pytrends` from `pyproject.toml` dependencies
- Remove conditional pytrends import
- Add `httpx` for async HTTP calls (already a dependency)

## 3. Detailed Implementation

### Step 1 — Remove pytrends import and HAS_PYTRENDS flag
Delete the conditional import block (lines 22-29):
```python
# DELETE THIS:
try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    HAS_PYTRENDS = False
```

### Step 2 — Add httpx import
```python
import httpx
```

### Step 3 — Rewrite `_fetch_trends()` to use RSS feed
Replace the entire `_fetch_trends()` method with a single RSS feed call:

```python
async def _fetch_trends(self) -> list[dict[str, Any]]:
    """Fetch trending searches from Google Trends RSS feed.
    
    Uses the official Google Trends RSS feed which returns real-time
    daily trending searches. Falls back to backup trends if the feed
    is unavailable.
    
    Returns:
        List of dicts with ``{"keyword": str, "score": float}``.
    """
    import xml.etree.ElementTree as ET

    url = f"https://trends.google.com/trending/rss?geo={self._geo}"
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        logger.warning(
            "Google Trends RSS feed request failed; trying backup trends.",
            exc_info=True,
        )
        return []

    try:
        root = ET.fromstring(response.text)
    except Exception:
        logger.warning(
            "Failed to parse Google Trends RSS feed.",
            exc_info=True,
        )
        return []

    ns = {"ht": "https://trends.google.com/trending/rss"}
    items = root.findall(".//item")
    
    if not items:
        logger.warning("Google Trends RSS feed returned no items.")
        return []

    results: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        title_el = item.find("title")
        if title_el is None or not title_el.text:
            continue
        keyword = title_el.text.strip()
        if not keyword:
            continue
        
        # Score: 100.0 for top trend, decreasing by 5 per entry
        score = max(100.0 - i * 5, 0.0)
        results.append({"keyword": keyword, "score": score})

    logger.info(
        "Fetched %d trends from Google RSS feed.",
        len(results),
    )
    return results
```

### Step 4 — Remove old parse methods
Delete these methods (no longer needed):
- `_parse_trending_searches()` 
- `_parse_realtime_trending()`
- `_parse_today_searches()`

### Step 5 — Remove `import pandas as pd`
Remove the `import pandas as pd` that was added.

### Step 6 — Update pyproject.toml
Remove `pytrends>=4.9.2` from dependencies (it was never a proper dependency anyway, just happened to be installed).

### Step 7 — Update tests
Rewrite tests to mock the RSS feed response instead of pytrends. The RSS feed XML format is:
```xml
<rss xmlns:ht="https://trends.google.com/trending/rss">
  <channel>
    <item>
      <title>flash flood warning</title>
      <ht:approx_traffic>2000+</ht:approx_traffic>
    </item>
    <item>
      <title>tennis scores today</title>
      <ht:approx_traffic>100000+</ht:approx_traffic>
    </item>
  </channel>
</rss>
```

## 4. Error Handling
- **HTTP errors** (4xx, 5xx): Caught by `response.raise_for_status()`, logged with traceback, returns empty list → triggers backup
- **Network timeouts**: httpx timeout of 15s, caught by generic Exception handler
- **XML parse errors**: Caught by `ET.fromstring()` exception handler
- **Empty feed**: If RSS returns no `<item>` elements, returns empty list
- **Missing titles**: Items without `<title>` elements are skipped

## 5. Input/Output Specifications
No changes to public interfaces. The `_fetch_trends()` method still returns `list[dict[str, Any]]` with `{"keyword": str, "score": float}`.

## 6. Edge Cases
- RSS feed returns items with empty titles → skip
- RSS feed XML structure changes → caught by XML parse error handler
- Network is down → caught by httpx exception handler
- Geo parameter results in different language feed → still works, titles will be in that language
- Rate limiting → Google RSS feed is publicly accessible without API keys, less likely to be rate-limited

## 7. Dependencies
- **Remove**: `pytrends` (dead library, archived)
- **Keep**: `httpx` (already in dependencies, used for async HTTP)
- **No new dependencies**: `xml.etree.ElementTree` is Python stdlib

## 8. Testing Requirements
### Integration test (REAL API call)
Create `tests/test_trend_selector_integration.py`:
```python
"""Integration test that actually calls the Google Trends RSS feed."""
import pytest
import pytest_asyncio
from modules.trend_selector import TrendSelector

@pytest.mark.integration
@pytest.mark.asyncio
async def test_rss_feed_returns_real_trends():
    """Actually calls the Google Trends RSS feed and verifies it returns data."""
    selector = TrendSelector(None, {"geo": "US"})
    # Temporarily set HAS_PYTRENDS to avoid the check
    import modules.trend_selector as ts
    ts.HAS_PYTRENDS = True
    
    results = await selector._fetch_trends()
    
    assert len(results) > 0, "RSS feed should return at least 1 trend"
    assert all("keyword" in r for r in results)
    assert all("score" in r for r in results)
    assert all(r["score"] > 0 for r in results)
    assert all(len(r["keyword"]) > 0 for r in results)
```

### Unit tests
Update existing tests to mock `httpx.AsyncClient.get()` instead of pytrends.

## 9. Deployment Considerations
- No database migration needed
- Remove pytrends from virtual environment: `pip uninstall pytrends`
- Rollback: revert code changes and reinstall pytrends
- Monitor: add logging for RSS feed fetch success/failure rates