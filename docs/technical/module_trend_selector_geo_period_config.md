# Trend Selector — Geo & Period Configuration

## 1. Feature Overview
**Purpose**: Make Google Trends geo location and timeframe configurable instead of hardcoded
**Business Value**: Allows targeting specific regions (USA) and matching trend period to scheduler interval (every 2 hours)
**Scope**: Add `geo` and `period` config keys to `backup_trends.yaml`, wire them into `TrendReq` initialization and API calls
**Success Criteria**: TrendSelector passes `pn` (geo) and timeframe to pytrends API based on config values; defaults to USA and "now 1-d" if not configured

## 2. Problem Statement

### Current State
- `TrendReq(hl="en-US", tz=360)` — `hl` is language, not geo. The `pn` parameter (e.g., `pn='united_states'`) is never set.
- No timeframe/period is passed to `trending_searches()` or `realtime_trending_searches()` — Google Trends defaults to "now 1-d" (past day)
- The scheduler runs every 2 hours (`IntervalTrigger(hours=2)`), but the trend period is not aligned with this cadence

### Required State
- Geo location should be configurable in `backup_trends.yaml` (e.g., `geo: "US"`)
- Period/timeframe should be configurable in `backup_trends.yaml` (e.g., `period: "now 1-d"`)
- `TrendReq` should pass `pn` parameter for geo targeting
- API calls should pass the configured timeframe

## 3. Service Ownership
**Primary Service**: `modules/trend_selector.py`
**Dependent Services**: `config/backup_trends.yaml` (config change), `tests/test_trend_selector.py` (test updates)
**Interface Changes**: None (internal config change only)

## 4. Detailed Implementation

### 4.1 Config Changes (`config/backup_trends.yaml`)

Add two new keys under the trend selection section:

```yaml
# Trend selection settings
trend_history_days: 30
geo: "US"              # NEW: Google Trends geo location (ISO country code)
period: "now 1-d"      # NEW: Google Trends timeframe (e.g., "now 1-d", "now 4-H", "today 1-m")
```

**Valid values for `geo`**:
- ISO 3166-1 alpha-2 country codes: `"US"`, `"GB"`, `"DE"`, etc.
- Empty string `""` for worldwide (no geo filter)
- Default: `"US"`

**Valid values for `period`**:
- Google Trends timeframe format: `"now 1-d"` (past day), `"now 4-H"` (past 4 hours), `"today 1-m"` (past month), etc.
- Default: `"now 1-d"`

### 4.2 Code Changes (`modules/trend_selector.py`)

#### Constructor Changes
Add `_geo` and `_period` instance variables:

```python
def __init__(self, db_pool: Any, config: dict[str, Any]) -> None:
    self._db = db_pool
    self._config = config
    self._backup_trends: list[dict[str, Any]] = config.get("backup_trends", [])
    self._history_days: int = config.get("trend_history_days", 30)
    self._geo: str = config.get("geo", "US")          # NEW
    self._period: str = config.get("period", "now 1-d")  # NEW
```

#### `_fetch_trends()` Changes
Pass `pn` and `period` to `TrendReq` and API calls:

```python
async def _fetch_trends(self) -> list[dict[str, Any]]:
    if not HAS_PYTRENDS:
        logger.warning("pytrends is not installed; skipping API fetch.")
        return []

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=30)
        return self._parse_trending_searches(pytrends)
    except Exception:
        logger.warning(
            "trending_searches() failed; trying realtime_trending_searches().",
            exc_info=True,
        )
        try:
            pytrends = TrendReq(hl="en-US", tz=360, timeout=30)
            return self._parse_realtime_trending(pytrends)
        except Exception:
            ...
```

Change to:

```python
async def _fetch_trends(self) -> list[dict[str, Any]]:
    if not HAS_PYTRENDS:
        logger.warning("pytrends is not installed; skipping API fetch.")
        return []

    try:
        pytrends = TrendReq(hl="en-US", tz=360, timeout=30, geo=self._geo)
        pytrends.build_payload(kw_list=[], timeframe=self._period)
        return self._parse_trending_searches(pytrends)
    except Exception:
        logger.warning(
            "trending_searches() failed; trying realtime_trending_searches().",
            exc_info=True,
        )
        try:
            pytrends = TrendReq(hl="en-US", tz=360, timeout=30, geo=self._geo)
            return self._parse_realtime_trending(pytrends)
        except Exception:
            ...
```

**Important**: The `pn` parameter in `TrendReq` constructor maps to geo. The `build_payload()` method accepts `timeframe` for period. The `realtime_trending_searches()` does not accept timeframe (it's always real-time), so `build_payload()` is only called before `trending_searches()`.

#### `_parse_trending_searches()` Changes
No signature change needed — the method already takes `pytrends` and calls `pytrends.trending_searches()`. The `build_payload()` call happens before this.

### 4.3 Test Changes (`tests/test_trend_selector.py`)

#### Update `sample_config` fixture
Add `geo` and `period` to the sample config:

```python
@pytest.fixture
def sample_config() -> dict:
    return {
        "backup_trends": [...],
        "trend_history_days": 30,
        "geo": "US",
        "period": "now 1-d",
    }
```

#### Update `_fetch_trends` tests
- Verify that `TrendReq` is called with `geo="US"` (or the configured value)
- Verify that `build_payload` is called with `timeframe="now 1-d"` (or the configured value)
- Add test for custom geo/period config values
- Add test for missing geo/period (should default to "US" and "now 1-d")

#### Update `TestRun` tests
- No changes needed if the mocked `TrendReq` already accepts kwargs (MagicMock accepts any call)

## 5. Error Handling

| Failure | Recovery |
|---------|----------|
| Invalid geo code | pytrends will return empty/error; falls through to realtime or backup |
| Invalid period format | pytrends will return empty/error; falls through to realtime or backup |
| Missing geo in config | Default to `"US"` |
| Missing period in config | Default to `"now 1-d"` |
| Empty string geo | Pass empty string — pytrends treats as worldwide |

## 6. Input/Output Specifications

### Config Input Validation
- `geo`: string, max 2 chars (ISO alpha-2), default `"US"`
- `period`: string, Google Trends timeframe format, default `"now 1-d"`
- No strict validation needed — let pytrends handle invalid values gracefully

### Logging
- INFO: Log the geo and period being used at debug level
- WARNING: Log if geo or period are missing from config (with defaults used)

## 7. Edge Cases

| Case | Expected Behavior |
|------|------------------|
| `geo: ""` (empty) | No geo filter — worldwide trends |
| `period: ""` (empty) | pytrends default (usually "now 1-d") |
| `geo: "XX"` (invalid) | pytrends returns empty; falls to backup |
| `period: "invalid"` | pytrends returns empty; falls to backup |
| Config has `geo` but no `period` | Use geo from config, default period |
| Config has `period` but no `geo` | Use period from config, default geo |
| Neither `geo` nor `period` in config | Both default values used |

## 8. Dependencies
- `config/backup_trends.yaml` — add two new keys
- `modules/trend_selector.py` — wire config into pytrends calls
- `tests/test_trend_selector.py` — update fixtures and add tests

## 9. Testing Requirements

### Unit Tests
- `test_uses_configured_geo`: Verify `TrendReq` called with configured geo value
- `test_uses_configured_period`: Verify `build_payload` called with configured timeframe
- `test_default_geo_when_missing`: Verify defaults to "US" when geo not in config
- `test_default_period_when_missing`: Verify defaults to "now 1-d" when period not in config
- `test_custom_geo_and_period`: Verify custom values are passed correctly
- `test_empty_geo_passed_through`: Verify empty string geo is passed as-is

### Existing Tests
- All existing tests should continue to pass (update `sample_config` fixture to include geo/period defaults)

## 10. Deployment Considerations
- **Migration**: None (config-only change)
- **Rollback**: Revert config and code
- **Monitoring**: No new metrics needed
- **Performance**: No impact
