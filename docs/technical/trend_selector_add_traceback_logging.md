# trend_selector_add_traceback_logging.md

## 1. Feature Overview
**Purpose**: Add exception traceback logging to all `except Exception` blocks in `modules/trend_selector.py` so that developers can diagnose why Google Trends API calls are failing.
**Business Value**: Currently, the pipeline silently falls back to backup trends without revealing the root cause of API failures. Adding tracebacks will enable faster debugging.
**Scope**: Only modify logging calls — no logic changes, no new behavior.
**Success Criteria**: Running `python main.py generate` produces full traceback output when API calls fail, showing the exact exception type and stack trace.

## 2. Service Ownership
**Primary Service**: `modules/trend_selector.py` (TrendSelector class)
**Dependent Services**: None
**Interface Changes**: None

## 3. Detailed Implementation
**Changes Required** — Add `exc_info=True` to 4 `logger.warning()` calls:

### Change 1: `_fetch_trends()` — Step 1 failure (line ~120)
**Current:**
```python
logger.warning(
    "realtime_trending_searches() failed; trying trending_searches()."
)
```
**New:**
```python
logger.warning(
    "realtime_trending_searches() failed; trying trending_searches().",
    exc_info=True,
)
```

### Change 2: `_fetch_trends()` — Step 2 failure (line ~130)
**Current:**
```python
logger.warning(
    "trending_searches() also failed; no API trends available."
)
```
**New:**
```python
logger.warning(
    "trending_searches() also failed; no API trends available.",
    exc_info=True,
)
```

### Change 3: `_parse_trending_searches()` — `interest_over_time()` failure (line ~145)
**Current:**
```python
logger.warning("interest_over_time() raised an exception.")
```
**New:**
```python
logger.warning("interest_over_time() raised an exception.", exc_info=True)
```

### Change 4: `_parse_realtime_trending()` — `realtime_trending_searches()` failure (line ~169)
**Current:**
```python
logger.warning("realtime_trending_searches() raised an exception.")
```
**New:**
```python
logger.warning("realtime_trending_searches() raised an exception.", exc_info=True)
```

## 4. Error Handling
No new error handling needed — this change only improves existing error logging.

## 5. Input/Output Specifications
No changes to inputs or outputs.

## 6. Edge Cases
- If `logger` is not configured with a handler that supports tracebacks, `exc_info=True` is still safe (it's a no-op in that case).
- If no exception is actually in context when `exc_info=True` is passed, Python's logging module handles it gracefully (logs `None`).

## 7. Dependencies
None.

## 8. Testing Requirements
- Run `python main.py generate` and verify that tracebacks appear in the log output when API calls fail.
- Run existing tests to ensure no regressions: `python -m pytest tests/test_trend_selector.py -v`

## 9. Deployment Considerations
- No migration needed.
- No rollback concerns — this is purely additive logging.
- Log volume will increase slightly (tracebacks are multi-line), but only on failure paths which are already rare.