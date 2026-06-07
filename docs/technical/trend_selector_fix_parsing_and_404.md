# trend_selector_fix_parsing_and_404.md

## 1. Feature Overview
**Purpose**: Fix two bugs in `modules/trend_selector.py` that prevent the Google Trends API from working:
1. **Bug A — `_parse_trending_searches()`**: Uses `df.iterrows()` index (a Pandas Timestamp) in arithmetic, causing `TypeError: unsupported operand type(s) for *: 'Timestamp' and 'int'`
2. **Bug B — `realtime_trending_searches()`**: Returns HTTP 404 from Google, likely because the pytrends library (v4.9.2) uses a stale endpoint URL

**Business Value**: The pipeline currently falls through to backup trends (which are all exhausted), resulting in `Pipeline skipped: no_trend_found`. Fixing these bugs will restore live trend fetching from Google.

**Scope**:
- Bug A: Fix `_parse_trending_searches()` to use `enumerate()` instead of `iterrows()` index
- Bug B: Upgrade pytrends to the latest version and/or switch to `today_searches()` as an additional fallback

**Success Criteria**: Running `python main.py generate` successfully fetches trends from Google without errors.

## 2. Service Ownership
**Primary Service**: `modules/trend_selector.py` (TrendSelector class)
**Dependent Services**: None
**Interface Changes**: None

## 3. Detailed Implementation

### Bug A — Fix `_parse_trending_searches()` (line 154)

**Root Cause**: `pytrends.interest_over_time()` returns a DataFrame with a **DatetimeIndex** (Pandas Timestamps). When iterating with `df.iterrows()`, the index variable `idx` is a `pd.Timestamp`, not an integer. The code then tries `idx * 5` which fails with `TypeError`.

**Current code (line 154):**
```python
for idx, row in df.iterrows():
    keyword = str(row.iloc[0]).strip()
    score = max(100.0 - idx * 5, 0.0)
```

**Fix:** Use `enumerate()` to get an integer counter:
```python
for i, (idx, row) in enumerate(df.iterrows()):
    keyword = str(row.iloc[0]).strip()
    score = max(100.0 - i * 5, 0.0)
```

### Bug B — Fix `realtime_trending_searches()` 404

**Root Cause**: pytrends v4.9.2 uses `https://trends.google.com/trends/api/realtimetrends` which returns HTTP 404. This endpoint has been deprecated/changed by Google.

**Fix approach**: Upgrade pytrends to the latest version and add `today_searches()` as a third fallback in `_fetch_trends()`.

**Step 1 — Upgrade pytrends:**
```bash
pip install --upgrade pytrends
```
Add `pytrends>=4.9.2` to `pyproject.toml` dependencies.

**Step 2 — Add `today_searches()` as third fallback in `_fetch_trends()`:**

After the existing Step 2 (trending_searches), add Step 3:
```python
# Step 3: Try today_searches() as final fallback
try:
    pytrends = TrendReq(hl="en-US", tz=360, timeout=30, geo=self._geo)
    return self._parse_today_searches(pytrends)
except Exception:
    logger.warning(
        "today_searches() also failed; no API trends available.",
        exc_info=True,
    )
    return []
```

**Step 3 — Add `_parse_today_searches()` static method:**
```python
@staticmethod
def _parse_today_searches(pytrends: Any) -> list[dict[str, Any]]:
    """Parse the Series returned by ``today_searches()``.
    
    ``today_searches()`` returns a pandas Series of trending search titles.
    Assigns a score of 100.0 to the top trend, decreasing by 5 for each
    subsequent trend.
    """
    try:
        series = pytrends.today_searches()
    except Exception:
        logger.warning("today_searches() raised an exception.", exc_info=True)
        raise

    if series is None or series.empty:
        return []

    results: list[dict[str, Any]] = []
    for i, value in enumerate(series):
        keyword = str(value).strip()
        if not keyword:
            continue
        score = max(100.0 - i * 5, 0.0)
        results.append({"keyword": keyword, "score": score})

    return results
```

## 4. Error Handling
- If pytrends upgrade doesn't fix the 404, `today_searches()` provides an alternative endpoint
- If all API methods fail, the existing backup fallback still works
- The `_parse_today_searches()` method handles empty/null Series gracefully

## 5. Input/Output Specifications
No changes to public interfaces. The `_parse_today_searches()` method follows the same pattern as existing parse methods.

## 6. Edge Cases
- `today_searches()` may return a Series with NaN values — handle with `str(value).strip()` and skip empty
- `today_searches()` may return an empty Series — return empty list
- If pytrends upgrade introduces breaking changes, the existing fallback chain still works

## 7. Dependencies
- `pytrends` — upgrade from 4.9.2 to latest (add explicit version to `pyproject.toml`)
- `pandas` — already installed as pytrends dependency

## 8. Testing Requirements
- Update `test_parse_trending_scores_decrease` test to properly mock `interest_over_time()` with a DatetimeIndex DataFrame (realistic mock)
- Add tests for `_parse_today_searches()`:
  - Normal case with multiple entries
  - Empty Series
  - Series with NaN/empty values
- Run all existing tests: `python -m pytest tests/test_trend_selector.py -v`

## 9. Deployment Considerations
- Run `pip install --upgrade pytrends` before deployment
- No database migration needed
- Rollback: revert the code changes and pin pytrends back to 4.9.2
- Monitor logs for any new API errors after upgrade